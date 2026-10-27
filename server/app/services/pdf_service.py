import io
from html import escape
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
    )
    REPORTLAB_AVAILABLE = True
    # Copper & Paper export palette matches the application.
    PRIMARY = colors.HexColor("#955137")
    PRIMARY_DARK = colors.HexColor("#955137")
    SECONDARY = colors.HexColor("#955137")
    NEUTRAL_DARK = colors.HexColor("#453C37")
    NEUTRAL_MID = colors.HexColor("#453C37")
    NEUTRAL_LIGHT = colors.HexColor("#FAF7F2")
    CARD_BG = colors.HexColor("#FAF7F2")
    BORDER_COLOR = colors.HexColor("#DED0C2")
except ImportError:
    REPORTLAB_AVAILABLE = False
    letter = None
    colors = None
    getSampleStyleSheet = None
    ParagraphStyle = None
    SimpleDocTemplate = Paragraph = Spacer = Table = TableStyle = PageBreak = KeepTogether = HRFlowable = None
    PRIMARY = PRIMARY_DARK = SECONDARY = NEUTRAL_DARK = NEUTRAL_MID = NEUTRAL_LIGHT = CARD_BG = BORDER_COLOR = None


def _export_data(value):
    """Escape untrusted report text and omit private generation instructions."""
    private = {"context_metadata", "generation_brief", "constructed_prompt", "system_prompt", "custom_instructions"}
    if isinstance(value, str):
        return escape(value, quote=False)
    if isinstance(value, dict):
        return {key: _export_data(item) for key, item in value.items() if key not in private}
    if isinstance(value, list):
        return [_export_data(item) for item in value]
    return value

class PDFService:
    @classmethod
    def is_available(cls) -> bool:
        """Returns True if the required reportlab export engine is installed and operational."""
        return REPORTLAB_AVAILABLE

    @staticmethod
    def _create_styles():
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name="CoverTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=NEUTRAL_DARK,
            alignment=0,
            spaceAfter=10
        ))
        styles.add(ParagraphStyle(
            name="CoverSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=14,
            leading=18,
            textColor=PRIMARY,
            spaceAfter=25
        ))
        styles.add(ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=PRIMARY_DARK,
            spaceBefore=15,
            spaceAfter=10,
            keepWithNext=True
        ))
        styles.add(ParagraphStyle(
            name="SubHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NEUTRAL_DARK,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True
        ))
        styles.add(ParagraphStyle(
            name="BodyDark",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=NEUTRAL_MID,
            spaceAfter=6
        ))
        styles.add(ParagraphStyle(
            name="BulletText",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=NEUTRAL_MID,
            leftIndent=12,
            spaceAfter=3
        ))
        styles.add(ParagraphStyle(
            name="TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.white,
            alignment=0
        ))
        styles.add(ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=NEUTRAL_MID,
            alignment=0
        ))
        return styles

    @classmethod
    def generate_full_project_pdf(
        cls,
        project_dict: Dict[str, Any],
        modules_data: Dict[str, Any],
        tasks_list: List[Dict[str, Any]]
    ) -> bytes:
        """
        Generates a consolidated enterprise blueprint PDF containing all active modules.
        Explicitly excludes version history, copilot conversations, and audit records.
        """
        if not cls.is_available():
            raise RuntimeError("PDF export dependency 'reportlab' is not installed or available.")
        project_dict = _export_data(project_dict)
        modules_data = _export_data(modules_data)
        tasks_list = _export_data(tasks_list)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        styles = cls._create_styles()
        story = []

        # --- COVER PAGE ---
        story.append(Spacer(1, 40))
        story.append(Paragraph("Venture Atlas", styles["CoverSubtitle"]))
        story.append(Paragraph("ENTERPRISE BLUEPRINT", ParagraphStyle(
            name="Badge", fontName="Helvetica-Bold", fontSize=10, textColor=PRIMARY, spaceAfter=15
        )))
        story.append(Paragraph(project_dict.get("name", "Project Blueprint"), styles["CoverTitle"]))
        
        stage_text = f"Business Stage: <b>{project_dict.get('stage', 'Idea')}</b>"
        if project_dict.get("industry"):
            stage_text += f" | Industry: <b>{project_dict.get('industry')}</b>"
        story.append(Paragraph(stage_text, styles["BodyDark"]))

        desc = project_dict.get("description", "Comprehensive structured business architecture and execution blueprint.")
        story.append(Paragraph(desc, styles["BodyDark"]))
        story.append(Spacer(1, 20))

        export_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
        meta_table = Table([
            ["Document Type:", "Executive Business Architecture & Operational Plan"],
            ["Generated On:", export_date],
            ["Generated By:", "Venture Atlas Planning Workspace"],
            ["Target Market:", project_dict.get("target_customers") or "Disclosed ICP"]
        ], colWidths=[120, 400])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,0), (0,-1), PRIMARY_DARK),
            ('TEXTCOLOR', (1,0), (1,-1), NEUTRAL_MID),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(meta_table)

        story.append(Spacer(1, 40))
        story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=20, spaceAfter=20))

        # Table of contents preview
        story.append(Paragraph("Table of Contents", styles["SubHeading"]))
        bmc_data_raw = modules_data.get("bmc")
        bmc_framework = (bmc_data_raw.get("framework_type") if isinstance(bmc_data_raw, dict) else None) or "standard_bmc"
        if bmc_framework == "lean_canvas":
            bmc_section_title = "2. Lean Canvas"
        elif bmc_framework == "value_prop_canvas":
            bmc_section_title = "2. Value Proposition Canvas"
        else:
            bmc_section_title = "2. Nine-Block Business Model Canvas"

        toc_items = [
            "1. Executive Project Overview",
            bmc_section_title,
            "3. Technology Stack & Architectural Blueprint",
            "4. Idea Validator & Feasibility Assessment",
            "5. Market Intelligence & Competitor Analysis",
            "6. Execution Roadmap & Timeline Milestones",
            "7. Detailed Operational Task Matrix"
        ]
        for item in toc_items:
            story.append(Paragraph(f"• {item}", styles["BodyDark"]))

        story.append(PageBreak())

        # --- SECTION 1: OVERVIEW ---
        story.append(Paragraph("1. Executive Project Overview", styles["SectionHeading"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_COLOR, spaceAfter=12))

        overview_data = [
            [Paragraph("<b>Parameter</b>", styles["TableHeader"]), Paragraph("<b>Details</b>", styles["TableHeader"])],
            [Paragraph("<b>Project Name</b>", styles["TableCell"]), Paragraph(str(project_dict.get("name", "")), styles["TableCell"])],
            [Paragraph("<b>Stage</b>", styles["TableCell"]), Paragraph(str(project_dict.get("stage", "")), styles["TableCell"])],
            [Paragraph("<b>Industry</b>", styles["TableCell"]), Paragraph(str(project_dict.get("industry", "Not specified")), styles["TableCell"])],
            [Paragraph("<b>Target Customers</b>", styles["TableCell"]), Paragraph(str(project_dict.get("target_customers", "Not specified")), styles["TableCell"])],
            [Paragraph("<b>Primary Goals</b>", styles["TableCell"]), Paragraph(str(project_dict.get("goals", "Not specified")), styles["TableCell"])],
            [Paragraph("<b>Budget Context</b>", styles["TableCell"]), Paragraph(str(project_dict.get("budget", "Not specified")), styles["TableCell"])],
        ]
        existing_stack = project_dict.get("existing_stack")
        if existing_stack and isinstance(existing_stack, dict):
            stack_str = ", ".join([f"{k}: {', '.join(v)}" for k, v in existing_stack.items() if v])
            if stack_str:
                overview_data.append([Paragraph("<b>Existing Stack</b>", styles["TableCell"]), Paragraph(stack_str, styles["TableCell"])])

        t_overview = Table(overview_data, colWidths=[140, 390])
        t_overview.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CARD_BG])
        ]))
        story.append(t_overview)
        story.append(Spacer(1, 20))

        # --- SECTION 2: BUSINESS MODEL CANVAS / FRAMEWORK ---
        bmc = modules_data.get("bmc")
        if bmc and isinstance(bmc, dict):
            story.append(PageBreak())
            story.append(Paragraph(bmc_section_title, styles["SectionHeading"]))
            story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_COLOR, spaceAfter=10))
            if bmc.get("tagline"):
                story.append(Paragraph(f"<i>Tagline: {bmc.get('tagline')}</i>", styles["BodyDark"]))
                story.append(Spacer(1, 10))

            if bmc_framework == "lean_canvas":
                blocks = [
                    ("1. Problem", bmc.get("problem", [])),
                    ("2. Solution", bmc.get("solution", [])),
                    ("3. Key Metrics", bmc.get("key_metrics", [])),
                    ("4. Unique Value Proposition", bmc.get("unique_value_proposition", [])),
                    ("5. Unfair Advantage", bmc.get("unfair_advantage", [])),
                    ("6. Channels", bmc.get("channels", [])),
                    ("7. Customer Segments", bmc.get("customer_segments", [])),
                    ("8. Cost Structure", bmc.get("cost_structure", [])),
                    ("9. Revenue Streams", bmc.get("revenue_streams", []))
                ]
                col_widths = [175, 175, 180]
                cols_per_row = 3
            elif bmc_framework == "value_prop_canvas":
                blocks = [
                    ("1. Customer Jobs", bmc.get("customer_jobs", [])),
                    ("2. Customer Pains", bmc.get("customer_pains") or bmc.get("pains") or []),
                    ("3. Customer Gains", bmc.get("customer_gains") or bmc.get("gains") or []),
                    ("4. Products & Services", bmc.get("products_and_services", [])),
                    ("5. Pain Relievers", bmc.get("pain_relievers", [])),
                    ("6. Gain Creators", bmc.get("gain_creators", []))
                ]
                col_widths = [265, 265]
                cols_per_row = 2
            else:
                blocks = [
                    ("1. Key Partnerships", bmc.get("key_partnerships", [])),
                    ("2. Key Activities", bmc.get("key_activities", [])),
                    ("3. Key Resources", bmc.get("key_resources", [])),
                    ("4. Value Propositions", bmc.get("value_propositions", [])),
                    ("5. Customer Relationships", bmc.get("customer_relationships", [])),
                    ("6. Channels", bmc.get("channels", [])),
                    ("7. Customer Segments", bmc.get("customer_segments", [])),
                    ("8. Cost Structure", bmc.get("cost_structure", [])),
                    ("9. Revenue Streams", bmc.get("revenue_streams", []))
                ]
                col_widths = [175, 175, 180]
                cols_per_row = 3

            grid_data = []
            for i in range(0, len(blocks), cols_per_row):
                row_blocks = blocks[i:i+cols_per_row]
                row_cells = []
                for title, items in row_blocks:
                    content_p = [Paragraph(f"<b>{title}</b>", styles["SubHeading"])]
                    for it in (items if isinstance(items, list) else [str(items)]):
                        content_p.append(Paragraph(f"• {it}", styles["BulletText"]))
                    row_cells.append(content_p)
                while len(row_cells) < cols_per_row:
                    row_cells.append([Paragraph("", styles["TableCell"])])
                grid_data.append(row_cells)

            t_bmc = Table(grid_data, colWidths=col_widths)
            t_bmc.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
                ('GRID', (0,0), (-1,-1), 0.8, BORDER_COLOR),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8)
            ]))
            story.append(t_bmc)
            story.append(Spacer(1, 20))

        # --- SECTION 3: TECHNOLOGY STACK ---
        tech = modules_data.get("tech_stack")
        if tech and isinstance(tech, dict):
            story.append(PageBreak())
            story.append(Paragraph("3. Technology Stack & Architecture", styles["SectionHeading"]))
            story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_COLOR, spaceAfter=10))

            if tech.get("summary"):
                story.append(Paragraph(f"<b>Architectural Summary:</b> {tech.get('summary')}", styles["BodyDark"]))
            if tech.get("architecture_pattern"):
                story.append(Paragraph(f"<b>Pattern:</b> {tech.get('architecture_pattern')}", styles["BodyDark"]))
            story.append(Spacer(1, 10))

            recs = tech.get("recommendations", [])
            if recs:
                table_rows = [
                    [Paragraph("<b>Category</b>", styles["TableHeader"]),
                     Paragraph("<b>Technology</b>", styles["TableHeader"]),
                     Paragraph("<b>Purpose & Suitability</b>", styles["TableHeader"]),
                     Paragraph("<b>Trade-offs & Migration Risk</b>", styles["TableHeader"])]
                ]
                for r in recs:
                    table_rows.append([
                        Paragraph(r.get("category", ""), styles["TableCell"]),
                        Paragraph(f"<b>{r.get('technology', '')}</b>", styles["TableCell"]),
                        Paragraph(f"{r.get('purpose', '')}<br/><i>{r.get('suitability', '')}</i>", styles["TableCell"]),
                        Paragraph(f"{r.get('trade_offs', 'None noted')}<br/>Risk: {r.get('migration_risk', 'Low')}", styles["TableCell"])
                    ])
                t_tech = Table(table_rows, colWidths=[90, 110, 170, 160])
                t_tech.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CARD_BG])
                ]))
                story.append(t_tech)
                story.append(Spacer(1, 20))

        # --- SECTION 4: IDEA VALIDATOR ---
        iv = modules_data.get("idea_validator")
        if iv and isinstance(iv, dict):
            story.append(PageBreak())
            story.append(Paragraph("4. Idea Validator & Feasibility Assessment", styles["SectionHeading"]))
            story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_COLOR, spaceAfter=10))

            score = iv.get("overall_viability_score")
            score_text = f"Overall Viability Score: {score}/100" if score is not None else "Overall Viability Score: Not assessed"
            story.append(Paragraph(f"<b>{score_text}</b>", styles["SubHeading"]))
            story.append(Paragraph(f"<b>Problem Clarity:</b> {iv.get('problem_clarity', '')}", styles["BodyDark"]))
            story.append(Paragraph(f"<b>Customer Fit:</b> {iv.get('customer_fit', '')}", styles["BodyDark"]))
            story.append(Paragraph(f"<b>Value Proposition:</b> {iv.get('value_proposition', '')}", styles["BodyDark"]))
            story.append(Paragraph(f"<b>Differentiation:</b> {iv.get('differentiation', '')}", styles["BodyDark"]))
            story.append(Spacer(1, 10))

            risks = iv.get("risks", [])
            if risks:
                story.append(Paragraph("Identified Risks & Mitigations", styles["SubHeading"]))
                risk_rows = [
                    [Paragraph("<b>Risk Description</b>", styles["TableHeader"]),
                     Paragraph("<b>Severity</b>", styles["TableHeader"]),
                     Paragraph("<b>Mitigation Strategy</b>", styles["TableHeader"])]
                ]
                for r in risks:
                    risk_rows.append([
                        Paragraph(r.get("risk", ""), styles["TableCell"]),
                        Paragraph(f"<b>{r.get('severity', '')}</b>", styles["TableCell"]),
                        Paragraph(r.get("mitigation", ""), styles["TableCell"])
                    ])
                t_risk = Table(risk_rows, colWidths=[200, 70, 260])
                t_risk.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
                    ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CARD_BG])
                ]))
                story.append(t_risk)
                story.append(Spacer(1, 15))

            experiments = iv.get("validation_experiments", [])
            if experiments:
                story.append(Paragraph("Recommended Validation Experiments", styles["SubHeading"]))
                for exp in experiments:
                    story.append(Paragraph(f"• <b>{exp.get('experiment')}</b> — Metric: {exp.get('metric')} (Target: {exp.get('target_criteria')})", styles["BulletText"]))
                story.append(Spacer(1, 15))

        # --- SECTION 5: MARKET RESEARCH ---
        mr = modules_data.get("market_research")
        if mr and isinstance(mr, dict):
            story.append(PageBreak())
            story.append(Paragraph("5. Market Research & Competitor Analysis", styles["SectionHeading"]))
            story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_COLOR, spaceAfter=10))

            story.append(Paragraph(f"<i>Provenance: {mr.get('provenance_note', 'Generated assessment')}</i>", styles["BodyDark"]))
            story.append(Paragraph(f"<b>Market Size & Dynamics:</b> {mr.get('target_market_size', '')}", styles["BodyDark"]))
            story.append(Paragraph(f"<b>Competitive Positioning:</b> {mr.get('competitive_positioning', '')}", styles["BodyDark"]))
            story.append(Spacer(1, 10))

            comps = mr.get("competitor_profiles", [])
            if comps:
                story.append(Paragraph("Competitor Profiles", styles["SubHeading"]))
                comp_rows = [
                    [Paragraph("<b>Competitor</b>", styles["TableHeader"]),
                     Paragraph("<b>Strengths</b>", styles["TableHeader"]),
                     Paragraph("<b>Weaknesses</b>", styles["TableHeader"]),
                     Paragraph("<b>Pricing / Share</b>", styles["TableHeader"])]
                ]
                for c in comps:
                    strengths = ", ".join(c.get("strengths", []))
                    weaknesses = ", ".join(c.get("weaknesses", []))
                    comp_rows.append([
                        Paragraph(f"<b>{c.get('name', '')}</b>", styles["TableCell"]),
                        Paragraph(strengths, styles["TableCell"]),
                        Paragraph(weaknesses, styles["TableCell"]),
                        Paragraph(f"{c.get('pricing_model', '')}<br/>{c.get('market_share_estimate', '')}", styles["TableCell"])
                    ])
                t_comp = Table(comp_rows, colWidths=[110, 150, 150, 120])
                t_comp.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
                    ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CARD_BG])
                ]))
                story.append(t_comp)
                story.append(Spacer(1, 15))

        # --- SECTION 6: EXECUTION ROADMAP & TASKS ---
        story.append(PageBreak())
        story.append(Paragraph("6. Execution Roadmap & Operational Task Matrix", styles["SectionHeading"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_COLOR, spaceAfter=10))

        if tasks_list:
            completed = sum(1 for t in tasks_list if t.get("status") in ("Finished", "Completed"))
            total = len(tasks_list)
            prog = int((completed / total) * 100) if total > 0 else 0
            story.append(Paragraph(f"<b>Total Execution Tasks:</b> {total} | <b>Completed:</b> {completed} | <b>Overall Progress:</b> {prog}%", styles["BodyDark"]))
            story.append(Spacer(1, 10))

            task_rows = [
                [Paragraph("<b>ID</b>", styles["TableHeader"]),
                 Paragraph("<b>Phase</b>", styles["TableHeader"]),
                 Paragraph("<b>Title & Deliverable</b>", styles["TableHeader"]),
                 Paragraph("<b>Timeline</b>", styles["TableHeader"]),
                 Paragraph("<b>Priority</b>", styles["TableHeader"]),
                 Paragraph("<b>Status</b>", styles["TableHeader"])]
            ]
            for t in tasks_list:
                details = []
                if t.get("branch_type") and t.get("branch_type") != "core":
                    details.append(f"Branch: {t.get('branch_type')}")
                if t.get("parent_outcome"):
                    details.append(f"Outcome: {t.get('parent_outcome')}")
                if t.get("deliverables"):
                    details.append(f"Deliverable: {t.get('deliverables')}")
                if t.get("definition_of_done"):
                    details.append(f"DoD: {t.get('definition_of_done')}")
                deliverable_text = f"<br/><i>{'; '.join(details)}</i>" if details else ""
                task_rows.append([
                    Paragraph(t.get("task_code", ""), styles["TableCell"]),
                    Paragraph(t.get("phase", ""), styles["TableCell"]),
                    Paragraph(f"<b>{t.get('title', '')}</b>{deliverable_text}", styles["TableCell"]),
                    Paragraph(f"{t.get('start_date', '')} to {t.get('end_date', '')} ({t.get('timeline', '')})", styles["TableCell"]),
                    Paragraph(t.get("priority", "Medium"), styles["TableCell"]),
                    Paragraph(f"<b>{t.get('status', 'Pending')}</b>", styles["TableCell"])
                ])
            t_tasks = Table(task_rows, colWidths=[45, 95, 170, 110, 50, 60])
            t_tasks.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), PRIMARY_DARK),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CARD_BG])
            ]))
            story.append(t_tasks)

        # Build document
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    @classmethod
    def generate_single_module_pdf(
        cls,
        project_dict: Dict[str, Any],
        module_type: str,
        module_data: Dict[str, Any]
    ) -> bytes:
        """Generates a PDF dedicated solely to the single specified module."""
        if not cls.is_available():
            raise RuntimeError("PDF export dependency 'reportlab' is not installed or available.")
        project_dict = _export_data(project_dict)
        module_data = _export_data(module_data)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        styles = cls._create_styles()
        story = []

        title_map = {
            "overview": "Project Overview",
            "bmc": "Business Model Canvas",
            "tech_stack": "Technology Stack Recommendations",
            "idea_validator": "Idea Validator Report",
            "market_research": "Market Research & Competitor Analysis",
            "execution_roadmap": "Execution Roadmap"
        }

        story.append(Paragraph(f"{project_dict.get('name', 'Project')} — {title_map.get(module_type, module_type)}", styles["CoverTitle"]))
        story.append(Paragraph(f"Business Stage: {project_dict.get('stage')} | Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y')}", styles["BodyDark"]))
        story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=10, spaceAfter=20))

        def append_value(label, value, depth=0):
            if label:
                title = escape(str(label).replace("_", " ").title(), quote=False)
                story.append(Paragraph(title, styles["SubHeading"] if depth < 2 else styles["BodyDark"]))
            if isinstance(value, dict):
                for key, item in value.items():
                    append_value(key, item, depth + 1)
            elif isinstance(value, list):
                for index, item in enumerate(value, 1):
                    if isinstance(item, (dict, list)):
                        append_value(f"Item {index}", item, depth + 1)
                    else:
                        story.append(Paragraph(f"• {item}", styles["BulletText"]))
            elif value is not None:
                story.append(Paragraph(str(value), styles["BodyDark"]))
            story.append(Spacer(1, 5))

        for key, value in module_data.items():
            append_value(key, value)

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
