"""
Business Architect — Process Manager & Launcher Helper
Cross-platform process lifecycle, port inspection, and safe termination utility.
"""

import sys
import os
import re
import json
import time
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PID_FILE = ROOT_DIR / ".app_pids"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173
BACKEND_HEALTH_URL = f"http://127.0.0.1:{BACKEND_PORT}/api/health"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"


def get_listening_pids(port: int):
    """Find all PIDs listening on a given TCP port using netstat."""
    pids = set()
    try:
        output = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        pattern = re.compile(rf":{port}\s+.*LISTENING\s+(\d+)", re.IGNORECASE)
        for line in output.splitlines():
            match = pattern.search(line)
            if match:
                pid = int(match.group(1))
                if pid > 0:
                    pids.add(pid)
    except Exception:
        pass
    return list(pids)


def get_process_info(pid: int):
    """Retrieve process executable name and command line using tasklist / wmic."""
    name = ""
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        if output and not "No tasks" in output:
            parts = output.strip().split('","')
            if parts:
                name = parts[0].strip('"').lower()
    except Exception:
        pass
    return name


def check_url(url: str, timeout: float = 2.0) -> bool:
    """Test if a URL returns HTTP 200 within timeout."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Business-Architect-Launcher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def cmd_check_backend():
    """Check if backend is healthy on port 8000."""
    if check_url(BACKEND_HEALTH_URL):
        print("healthy")
        return 0
    else:
        print("down")
        return 1


def cmd_check_frontend():
    """Check if frontend is serving on port 5173."""
    if check_url(FRONTEND_URL):
        print("healthy")
        return 0
    else:
        print("down")
        return 1


def cmd_check_prereqs():
    """Validate backend Python dependencies and environment files without exposing secrets."""
    errors = []
    
    # 1. Check Python packages
    required_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("sqlalchemy", "SQLAlchemy"),
        ("alembic", "Alembic"),
        ("argon2", "Argon2-cffi"),
        ("google.genai", "Google GenAI SDK"),
        ("reportlab", "ReportLab")
    ]
    for mod_name, label in required_packages:
        try:
            __import__(mod_name)
        except ImportError:
            errors.append(f"Missing Python package: {label} ({mod_name})")

    # 2. Check environment file
    env_file = ROOT_DIR / ".env"
    server_env = ROOT_DIR / "server" / ".env"
    target_env = env_file if env_file.exists() else (server_env if server_env.exists() else None)

    if not target_env:
        print("[NOTICE] Neither .env nor server/.env was found.")
        print("[NOTICE] Creating default .env from .env.example...")
        example_env = ROOT_DIR / ".env.example"
        if example_env.exists():
            try:
                import shutil
                shutil.copyfile(example_env, env_file)
                print("[OK] Created .env from .env.example")
            except Exception as e:
                errors.append(f"Could not create .env from .env.example: {e}")
        target_env = env_file

    gemini_key_status = "Not configured"
    if target_env and target_env.exists():
        try:
            with open(target_env, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                match = re.search(r"^\s*GEMINI_API_KEY\s*=\s*(.+)$", content, re.MULTILINE)
                if match:
                    val = match.group(1).strip().strip("'\"")
                    if val and val != "your_gemini_api_key_here":
                        gemini_key_status = "Configured (verified)"
                    else:
                        gemini_key_status = "Placeholder / empty"
        except Exception:
            pass

    print(f"[INFO] Gemini AI API Key: {gemini_key_status}")

    if errors:
        print("\n[ERROR] Missing prerequisites detected:")
        for err in errors:
            print(f"  - {err}")
        print("\nTo fix Python dependencies, run:")
        print(f'  cd /d "{ROOT_DIR / "server"}"')
        print('  python -m pip install -r requirements.txt\n')
        return 1

    print("[OK] All backend dependencies verified successfully.")
    return 0


def cmd_wait_ready(timeout: int = 35):
    """Wait for both backend and frontend to respond within timeout seconds."""
    print("[INFO] Waiting for backend and frontend services to initialize...")
    start_time = time.time()
    backend_ok = False
    frontend_ok = False

    while time.time() - start_time < timeout:
        elapsed = int(time.time() - start_time)
        if not backend_ok:
            backend_ok = check_url(BACKEND_HEALTH_URL, timeout=1.5)
        if not frontend_ok:
            frontend_ok = check_url(FRONTEND_URL, timeout=1.5)

        if backend_ok and frontend_ok:
            print(f"\n[OK] Backend healthy ({BACKEND_HEALTH_URL})")
            print(f"[OK] Frontend ready ({FRONTEND_URL})")
            # Save PIDs
            cmd_save_pids()
            return 0

        dots = "." * ((elapsed % 4) + 1)
        b_status = "ready" if backend_ok else "starting"
        f_status = "ready" if frontend_ok else "starting"
        sys.stdout.write(f"\r  [{elapsed:2d}s] Backend ({b_status}), Frontend ({f_status}){dots:<4}")
        sys.stdout.flush()
        time.sleep(1)

    print("\n\n[ERROR] Application failed to become ready within the timeout period.")
    if not backend_ok:
        print(f"  - Backend did not respond on {BACKEND_HEALTH_URL}")
        print("    Check the 'AI Business Architect - Backend' window for tracebacks.")
    if not frontend_ok:
        print(f"  - Frontend did not respond on {FRONTEND_URL}")
        print("    Check the 'AI Business Architect - Frontend' window for Vite errors.")
    return 1


def cmd_save_pids():
    """Identify and persist backend and frontend PIDs."""
    backend_pids = get_listening_pids(BACKEND_PORT)
    frontend_pids = get_listening_pids(FRONTEND_PORT)

    data = {
        "backend_pids": backend_pids,
        "frontend_pids": frontend_pids,
        "backend_port": BACKEND_PORT,
        "frontend_port": FRONTEND_PORT,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def is_app_process(pid: int) -> bool:
    """Validate that the process belongs to AI Business Architect."""
    try:
        cmd = f'powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \\"ProcessId = {pid}\\").CommandLine"'
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True).strip().lower()
        if any(marker in out for marker in ("businessarchitect", "uvicorn", "vite", "app.main:app")):
            return True
    except Exception:
        pass
    return False


def cmd_stop():
    """Safely terminate ONLY verified AI Business Architect processes."""
    stored_pids = set()

    # 1. Read stored PIDs if file exists
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for pid in data.get("backend_pids", []):
                    stored_pids.add(int(pid))
                for pid in data.get("frontend_pids", []):
                    stored_pids.add(int(pid))
        except Exception:
            pass

    # 2. Inspect active port listeners on 8000 and 5173
    current_backend = get_listening_pids(BACKEND_PORT)
    current_frontend = get_listening_pids(FRONTEND_PORT)

    all_candidate_pids = set(stored_pids)
    all_candidate_pids.update(current_backend)
    all_candidate_pids.update(current_frontend)

    stopped_count = 0

    for pid in list(all_candidate_pids):
        pname = get_process_info(pid)
        if not pname:
            continue

        # Verify identity: must either be in stored PIDs or match app command line
        is_verified = (pid in stored_pids) or is_app_process(pid)

        if is_verified and pname in ("python.exe", "pythonw.exe", "node.exe", "cmd.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
                print(f"[OK] Safely stopped {pname} service (PID {pid})")
                stopped_count += 1
            except Exception as e:
                print(f"[WARNING] Could not terminate PID {pid}: {e}")
        elif pname:
            print(f"[SKIP] PID {pid} is '{pname}', unverified ownership. Preserving process.")

    # Clean up PID file
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass

    if stopped_count == 0:
        print("[INFO] AI Business Architect is not currently running.")
        print(f"       No active services found listening on port {BACKEND_PORT} or {FRONTEND_PORT}.")
    else:
        print(f"\n[SUCCESS] Successfully stopped {stopped_count} AI Business Architect process(es).")
    return 0


def cmd_find_chrome():
    """Locate Google Chrome executable on Windows."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]

    for path in candidates:
        if os.path.isfile(path):
            print(path)
            return 0

    # Registry check
    try:
        cmd = ['reg', 'query', r'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe', '/ve']
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        for line in out.splitlines():
            if "REG_SZ" in line:
                val = line.split("REG_SZ")[-1].strip()
                if os.path.isfile(val):
                    print(val)
                    return 0
    except Exception:
        pass

    # Check PATH
    try:
        out = subprocess.check_output(["where", "chrome"], stderr=subprocess.DEVNULL, text=True)
        first_line = out.strip().splitlines()[0]
        if os.path.isfile(first_line):
            print(first_line)
            return 0
    except Exception:
        pass

    return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app_manager.py [check-prereqs|check-backend|check-frontend|wait-ready|save-pids|stop|find-chrome]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "check-prereqs":
        sys.exit(cmd_check_prereqs())
    elif cmd == "check-backend":
        sys.exit(cmd_check_backend())
    elif cmd == "check-frontend":
        sys.exit(cmd_check_frontend())
    elif cmd == "wait-ready":
        sys.exit(cmd_wait_ready())
    elif cmd == "save-pids":
        cmd_save_pids()
        sys.exit(0)
    elif cmd == "stop":
        sys.exit(cmd_stop())
    elif cmd == "find-chrome":
        sys.exit(cmd_find_chrome())
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
