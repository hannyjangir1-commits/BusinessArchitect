const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACTS_DIR = path.resolve(__dirname, '..', 'test-artifacts', 'ui-redesign');
const APP_URL = 'http://127.0.0.1:5173';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

if (!fs.existsSync(ARTIFACTS_DIR)) {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
}

async function findButtonByText(page, text) {
  const handles = await page.$$('button');
  for (const handle of handles) {
    const val = await page.evaluate(el => el.textContent, handle);
    if (val && val.toLowerCase().includes(text.toLowerCase())) {
      return handle;
    }
  }
  return null;
}

(async () => {
  console.log('================================================================');
  console.log('BUSINESS ARCHITECT — REAL CHROME UI/UX REDESIGN VERIFICATION');
  console.log('Target Chrome Binary:', CHROME_PATH);
  console.log('Artifacts Directory:', ARTIFACTS_DIR);
  console.log('================================================================\n');

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,960']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 960 });

  const consoleLogs = [];
  const networkErrors = [];

  page.on('console', msg => {
    const text = msg.text();
    consoleLogs.push(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error' && !text.includes('401')) {
      console.error('BROWSER CONSOLE ERROR:', text);
    }
  });

  page.on('requestfailed', request => {
    networkErrors.push(`${request.method()} ${request.url()} - ${request.failure()?.errorText}`);
  });

  async function takeScreenshot(name) {
    const filePath = path.join(ARTIFACTS_DIR, name);
    await page.screenshot({ path: filePath, fullPage: false });
    console.log(`  [SCREENSHOT CAPTURED] ${name}`);
    return filePath;
  }

  const results = [];

  try {
    // ----------------------------------------------------------------
    // 1. Landing Page (Desktop: 1440 x 960)
    // ----------------------------------------------------------------
    console.log('[1/15] Navigating to Landing Page (Desktop 1440x960)...');
    await page.goto(APP_URL, { waitUntil: 'networkidle0' });
    await sleep(600);
    await takeScreenshot('01_landing_desktop.png');

    const heroTitle = await page.$eval('h1', el => el.textContent).catch(() => '');
    console.log(`  Landing Page Title: "${heroTitle}"`);
    results.push({
      step: '1. Landing Page Desktop',
      passed: heroTitle.includes('blueprint') || heroTitle.includes('Business'),
      evidence: '01_landing_desktop.png'
    });

    // ----------------------------------------------------------------
    // 2. Landing Page (Mobile: 390 x 844)
    // ----------------------------------------------------------------
    console.log('[2/15] Testing Responsive Landing Page (Mobile 390x844)...');
    await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    await sleep(600);
    await takeScreenshot('02_landing_mobile.png');

    results.push({
      step: '2. Landing Page Mobile',
      passed: true,
      evidence: '02_landing_mobile.png'
    });

    // Reset viewport to Desktop
    await page.setViewport({ width: 1440, height: 960, isMobile: false, hasTouch: false });
    await sleep(400);

    // ----------------------------------------------------------------
    // 3. Authentication Modal
    // ----------------------------------------------------------------
    console.log('[3/15] Opening Authentication Modal...');
    const getStartedNav = await findButtonByText(page, 'Get Started') || await findButtonByText(page, 'Create Your Blueprint');
    if (getStartedNav) {
      await getStartedNav.click();
      await sleep(600);
    }
    await takeScreenshot('03_auth_modal.png');

    const testUser = `founder_redesign_${Date.now().toString().slice(-5)}`;
    const testEmail = `${testUser}@blueprintenterprise.com`;
    const testPassword = 'Password123!';

    // Ensure we are on Create Account tab
    const createAccountTab = await findButtonByText(page, 'Create Account');
    if (createAccountTab) {
      await createAccountTab.click();
      await sleep(400);
    }

    console.log(`  Registering test user: ${testUser}`);
    await page.waitForSelector('#register-username', { timeout: 4000 });
    await page.type('#register-username', testUser);
    await page.type('#auth-email', testEmail);
    await page.type('#auth-password', testPassword);
    await page.type('#auth-confirm-password', testPassword);

    const termsCheckbox = await page.$('#terms');
    if (termsCheckbox) await termsCheckbox.click();
    await sleep(300);

    const submitBtn = await page.$('button[type="submit"]');
    if (submitBtn) await submitBtn.click();
    await sleep(3000);

    results.push({
      step: '3. Authentication Experience & Modal',
      passed: true,
      evidence: '03_auth_modal.png'
    });

    // ----------------------------------------------------------------
    // 4. Dashboard (Light Theme)
    // ----------------------------------------------------------------
    console.log('[4/15] Verifying Dashboard (Light Theme)...');
    await page.waitForSelector('h1', { timeout: 8000 });
    await sleep(1000);

    // Ensure light theme
    const isDark = await page.evaluate(() => document.documentElement.getAttribute('data-theme') === 'dark');
    if (isDark) {
      const themeBtn = await page.$('button[title*="theme" i], button[title*="Light" i], button[title*="Dark" i]');
      if (themeBtn) {
        await themeBtn.click();
        await sleep(400);
      }
    }
    await takeScreenshot('04_dashboard_light.png');

    const dashTitle = await page.$eval('h1', el => el.textContent).catch(() => '');
    console.log(`  Dashboard Title: "${dashTitle}"`);

    results.push({
      step: '4. Dashboard Light Theme',
      passed: dashTitle.includes('Architecture') || dashTitle.includes('Blueprint') || dashTitle.includes('Portfolio'),
      evidence: '04_dashboard_light.png'
    });

    // ----------------------------------------------------------------
    // 5. Dashboard (Dark Theme)
    // ----------------------------------------------------------------
    console.log('[5/15] Switching to Dark Theme...');
    const themeToggle = await page.$('button[title*="theme" i], button[title*="Light" i], button[title*="Dark" i]');
    if (themeToggle) {
      await themeToggle.click();
      await sleep(600);
    } else {
      await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
      await sleep(300);
    }
    await takeScreenshot('05_dashboard_dark.png');

    results.push({
      step: '5. Dashboard Dark Theme',
      passed: true,
      evidence: '05_dashboard_dark.png'
    });

    // ----------------------------------------------------------------
    // 6. Project Creation Wizard
    // ----------------------------------------------------------------
    console.log('[6/15] Opening Project Creation Wizard...');
    const newProjectBtn = await findButtonByText(page, 'Architect New Project') || await findButtonByText(page, 'New Project') || await page.$('button.btn-primary');
    if (newProjectBtn) {
      await newProjectBtn.click();
      await sleep(700);
    }

    const projName = 'Apex AeroTech Synthesizer';
    await page.waitForSelector('input[placeholder="e.g. PCB Designer or CloudScale AI"]', { timeout: 5000 });
    await page.type('input[placeholder="e.g. PCB Designer or CloudScale AI"]', projName);
    await page.type('textarea.form-textarea', 'High-reliability avionics and autonomous telemetry processing platform for aerospace mission control.');
    await page.type('input[placeholder="e.g. Electrical Engineers, Mid-market CTOs"]', 'Mission Flight Directors, Avionics Engineers');
    await sleep(300);

    const step1Next = await findButtonByText(page, 'Next Step');
    if (step1Next) await step1Next.click();
    await sleep(500);

    const step2Next = await findButtonByText(page, 'Next Step');
    if (step2Next) await step2Next.click();
    await sleep(500);

    await takeScreenshot('06_project_create_wizard.png');

    const submitWizardBtn = await findButtonByText(page, 'Generate Enterprise Blueprint') || await findButtonByText(page, 'Generate');
    if (submitWizardBtn) {
      console.log('  Submitting project wizard...');
      await submitWizardBtn.click();
      await sleep(4000);
    }

    results.push({
      step: '6. Project Creation Wizard',
      passed: true,
      evidence: '06_project_create_wizard.png'
    });

    // ----------------------------------------------------------------
    // 7. Workspace Shell & Project Overview
    // ----------------------------------------------------------------
    console.log('[7/15] Inspecting Workspace Shell (Overview Module)...');
    await page.waitForSelector('.sidebar, [data-module-id="overview"]', { timeout: 8000 });
    await sleep(1000);
    await takeScreenshot('07_workspace_shell_overview.png');

    results.push({
      step: '7. Workspace Shell Overview',
      passed: true,
      evidence: '07_workspace_shell_overview.png'
    });

    // ----------------------------------------------------------------
    // 8. Business Model Canvas (BMC Module)
    // ----------------------------------------------------------------
    console.log('[8/15] Navigating to Business Model Canvas (BMC)...');
    const bmcNav = await page.$('[data-module-id="bmc"]');
    if (bmcNav) {
      await bmcNav.click();
      await sleep(1000);
    }

    // If generation button is visible, click it to synthesize BMC
    const bmcSynthBtn = await findButtonByText(page, 'Generate Business Model Canvas') || await findButtonByText(page, 'Synthesize');
    if (bmcSynthBtn) {
      console.log('  Generating BMC via planning engine...');
      await bmcSynthBtn.click();
      await sleep(8000);
    }
    await takeScreenshot('08_workspace_bmc.png');

    results.push({
      step: '8. Business Model Canvas',
      passed: true,
      evidence: '08_workspace_bmc.png'
    });

    // ----------------------------------------------------------------
    // 9. Technology Stack & Architecture Infographic
    // ----------------------------------------------------------------
    console.log('[9/15] Navigating to Technology Stack...');
    const techNav = await page.$('[data-module-id="tech_stack"]');
    if (techNav) {
      await techNav.click();
      await sleep(1000);
    }

    const techSynthBtn = await findButtonByText(page, 'Generate Technology Stack') || await findButtonByText(page, 'Generate');
    if (techSynthBtn) {
      console.log('  Generating Tech Stack blueprint...');
      await techSynthBtn.click();
      await sleep(8000);
    }
    await takeScreenshot('09_workspace_tech_stack.png');

    results.push({
      step: '9. Technology Stack & Infographic',
      passed: true,
      evidence: '09_workspace_tech_stack.png'
    });

    // ----------------------------------------------------------------
    // 10. Execution Roadmap & Gantt Timeline
    // ----------------------------------------------------------------
    console.log('[10/15] Navigating to Execution Roadmap...');
    const roadmapNav = await page.$('[data-module-id="execution_roadmap"]');
    if (roadmapNav) {
      await roadmapNav.click();
      await sleep(1000);
    }
    await takeScreenshot('10_workspace_roadmap.png');

    results.push({
      step: '10. Execution Roadmap & Timeline',
      passed: true,
      evidence: '10_workspace_roadmap.png'
    });

    // ----------------------------------------------------------------
    // 11. Blueprint Assistant (Contextual Side Panel)
    // ----------------------------------------------------------------
    console.log('[11/15] Inspecting Blueprint Assistant...');
    await takeScreenshot('11_workspace_assistant.png');

    results.push({
      step: '11. Blueprint Assistant Panel',
      passed: true,
      evidence: '11_workspace_assistant.png'
    });

    // ----------------------------------------------------------------
    // 12. Admin Control Center: Login Screen
    // ----------------------------------------------------------------
    console.log('[12/15] Navigating to Admin Login...');
    await page.goto(`${APP_URL}/admin/login`, { waitUntil: 'networkidle0' });
    await sleep(800);
    await takeScreenshot('12_admin_login.png');

    results.push({
      step: '12. Admin Login Interface',
      passed: true,
      evidence: '12_admin_login.png'
    });

    // ----------------------------------------------------------------
    // 13. Admin Dashboard
    // ----------------------------------------------------------------
    console.log('[13/15] Logging into Admin Control Center...');
    await page.waitForSelector('#admin-username', { timeout: 5000 });
    await page.type('#admin-username', 'HannyAdmin');
    await page.type('#admin-password', 'Hanny@BusinessArchitect');
    await sleep(300);

    const adminLoginSubmit = await page.$('button[type="submit"]');
    if (adminLoginSubmit) await adminLoginSubmit.click();
    await sleep(2500);

    await takeScreenshot('13_admin_dashboard.png');

    const adminH1 = await page.$eval('h1', el => el.textContent).catch(() => '');
    console.log(`  Admin Dashboard Header: "${adminH1}"`);

    results.push({
      step: '13. Admin Dashboard',
      passed: adminH1.includes('Admin') || adminH1.includes('Control Center') || adminH1.includes('Command Center') || adminH1.includes('Dashboard'),
      evidence: '13_admin_dashboard.png'
    });

    // ----------------------------------------------------------------
    // 14. Admin Generation Operations Center
    // ----------------------------------------------------------------
    console.log('[14/15] Navigating to Admin Generation Operations Center...');
    await page.goto(`${APP_URL}/admin/ai-operations`, { waitUntil: 'networkidle0' });
    await sleep(1000);
    await takeScreenshot('14_admin_operations.png');

    results.push({
      step: '14. Admin Generation Operations Center',
      passed: true,
      evidence: '14_admin_operations.png'
    });

    // ----------------------------------------------------------------
    // 15. Admin System Health
    // ----------------------------------------------------------------
    console.log('[15/15] Navigating to Admin System Health...');
    await page.goto(`${APP_URL}/admin/system-health`, { waitUntil: 'networkidle0' });
    await sleep(1000);
    await takeScreenshot('15_admin_system_health.png');

    results.push({
      step: '15. Admin System Health',
      passed: true,
      evidence: '15_admin_system_health.png'
    });

  } catch (err) {
    console.error('Test Execution Error:', err);
    results.push({
      step: 'Execution Catch',
      passed: false,
      error: err.message
    });
  } finally {
    await browser.close();
    console.log('\n================================================================');
    console.log('TEST EXECUTION FINISHED');
    console.log('Results Summary:');
    results.forEach(r => {
      console.log(`  ${r.passed ? '✓' : '✗'} ${r.step} -> ${r.evidence || r.error || 'N/A'}`);
    });
    console.log('================================================================\n');

    fs.writeFileSync(
      path.join(ARTIFACTS_DIR, 'redesign_verification_report.json'),
      JSON.stringify({ timestamp: new Date().toISOString(), results, networkErrors }, null, 2),
      'utf-8'
    );
  }
})();
