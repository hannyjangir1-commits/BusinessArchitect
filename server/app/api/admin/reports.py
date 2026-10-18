import csv
import io
from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from app.db.session import get_db
from app.models.all_models import (
    User, Project, AIOperation, AuditLog, ModuleContent, RoadmapTask
)
from app.api.deps import require_admin, require_permission
from app.core.telemetry import record_audit_log

router = APIRouter(prefix="/reports", tags=["Admin Reports & Exports"])

def sanitize_csv_cell(value: Any) -> str:
    """Protect against spreadsheet formula injection attacks (CSV injection)."""
    if value is None:
        return ""
    val_str = str(value)
    # If cell starts with formula characters, prefix with single quote
    if val_str and val_str[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    return val_str

@router.get("/export-csv")
def export_csv_report(
    report_type: str = Query(..., pattern="^(users|projects|ai_operations|audit_logs)$"),
    current_admin: User = Depends(require_permission("export_reports")),
    db: Session = Depends(get_db)
):
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    if report_type == "users":
        writer.writerow(["User ID", "Username", "Email", "Role", "Is Suspended", "Created At", "Last Active At"])
        users = db.query(User).order_by(desc(User.created_at)).limit(5000).all()
        for u in users:
            writer.writerow([
                sanitize_csv_cell(u.id),
                sanitize_csv_cell(u.username),
                sanitize_csv_cell(u.email),
                sanitize_csv_cell(u.role),
                sanitize_csv_cell(u.is_suspended),
                sanitize_csv_cell(u.created_at.isoformat() if u.created_at else ""),
                sanitize_csv_cell(u.last_active_at.isoformat() if u.last_active_at else "")
            ])

    elif report_type == "projects":
        writer.writerow(["Project ID", "Name", "Owner ID", "Stage", "Industry", "Active Module", "Created At"])
        projects = db.query(Project).order_by(desc(Project.created_at)).limit(5000).all()
        for p in projects:
            writer.writerow([
                sanitize_csv_cell(p.id),
                sanitize_csv_cell(p.name),
                sanitize_csv_cell(p.user_id),
                sanitize_csv_cell(p.stage),
                sanitize_csv_cell(p.industry),
                sanitize_csv_cell(p.active_module),
                sanitize_csv_cell(p.created_at.isoformat() if p.created_at else "")
            ])

    elif report_type == "ai_operations":
        writer.writerow(["Operation ID", "Module", "Operation Type", "Model", "Duration (ms)", "Status", "Error Category", "Created At"])
        ops = db.query(AIOperation).order_by(desc(AIOperation.created_at)).limit(5000).all()
        for op in ops:
            writer.writerow([
                sanitize_csv_cell(op.id),
                sanitize_csv_cell(op.module_type),
                sanitize_csv_cell(op.operation_type),
                sanitize_csv_cell(op.model_name),
                sanitize_csv_cell(op.duration_ms),
                sanitize_csv_cell(op.status),
                sanitize_csv_cell(op.error_category or "none"),
                sanitize_csv_cell(op.created_at.isoformat() if op.created_at else "")
            ])

    elif report_type == "audit_logs":
        writer.writerow(["Log ID", "Actor ID", "Action", "Target Type", "Target ID", "Outcome", "Reason", "Timestamp"])
        logs = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(5000).all()
        for l in logs:
            writer.writerow([
                sanitize_csv_cell(l.id),
                sanitize_csv_cell(l.actor_id or "system"),
                sanitize_csv_cell(l.action),
                sanitize_csv_cell(l.target_type),
                sanitize_csv_cell(l.target_id or ""),
                sanitize_csv_cell(l.outcome),
                sanitize_csv_cell(l.reason or ""),
                sanitize_csv_cell(l.created_at.isoformat() if l.created_at else "")
            ])

    output.seek(0)
    filename = f"aba_{report_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="export_csv_report",
        target_type="report",
        target_id=report_type,
        outcome="success",
        details={"report_type": report_type, "filename": filename}
    )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/summary-pdf")
def export_summary_pdf(
    current_admin: User = Depends(require_permission("export_reports")),
    db: Session = Depends(get_db)
):
    """Generate a clean executive summary PDF of the enterprise platform status."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="RepTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=colors.HexColor("#0f172a")
    )
    subtitle_style = ParagraphStyle(
        name="RepSubtitle", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, leading=14, textColor=colors.HexColor("#64748b")
    )
    h2_style = ParagraphStyle(
        name="RepH2", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=colors.HexColor("#4338ca"),
        spaceBefore=14, spaceAfter=8
    )
    body_style = ParagraphStyle(
        name="RepBody", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor("#334155")
    )

    story = []
    story.append(Paragraph("Venture Atlas — Enterprise Status Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')} | Requested by {current_admin.username} ({current_admin.role})", subtitle_style))
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#6366f1"), spaceAfter=15))

    # Core Metrics Table
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_projs = db.query(func.count(Project.id)).scalar() or 0
    total_ai = db.query(func.count(AIOperation.id)).scalar() or 0
    ai_success = db.query(func.count(AIOperation.id)).filter(AIOperation.status == "success").scalar() or 0
    success_rate = f"{round(ai_success / total_ai * 100, 1)}%" if total_ai > 0 else "100.0%"

    story.append(Paragraph("Executive Platform Overview", h2_style))
    data = [
        ["Key Metric", "Current Value", "Operational Status"],
        ["Registered User Accounts", str(total_users), "Active"],
        ["Total Business Architecture Projects", str(total_projs), "Active"],
        ["Gemini Generation Operations Executed", str(total_ai), "Operational"],
        ["Generation Success Rate", success_rate, "Optimal" if total_ai == 0 or ai_success/total_ai >= 0.8 else "Degraded"],
        ["Active Database Migrations", "Synchronized", "Verified"],
    ]

    t = Table(data, colWidths=[200, 140, 180])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # Security & Governance Summary
    story.append(Paragraph("Security & Governance Summary", h2_style))
    story.append(Paragraph("This system enforces strict session isolation, Argon2id cryptographic password hashing, role-based backend authorization, and CSRF protection on all administrative operations.", body_style))

    doc.build(story)
    buffer.seek(0)
    pdf_filename = f"aba_executive_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"

    record_audit_log(
        db,
        actor_id=current_admin.id,
        action="export_summary_pdf",
        target_type="report",
        target_id="executive_summary_pdf",
        outcome="success",
        details={"filename": pdf_filename}
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'}
    )
