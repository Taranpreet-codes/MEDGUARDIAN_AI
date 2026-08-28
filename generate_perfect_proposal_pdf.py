import os
import sys
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor('#0f766e')) # Deep Teal
        
        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(40, 755, "MedGuardian AI -- Startup & Clinical Proposal")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor('#64748b'))
            self.drawRightString(572, 755, "STUDENT FOUNDER & VENTURE EDITION")
            self.setStrokeColor(colors.HexColor('#cbd5e1'))
            self.setLineWidth(0.5)
            self.line(40, 748, 572, 748)

        # Footer (All pages)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#64748b'))
        self.setStrokeColor(colors.HexColor('#e2e8f0'))
        self.setLineWidth(0.5)
        self.line(40, 38, 572, 38)
        
        self.drawString(40, 26, f"MedGuardian AI (c) {datetime.date.today().year} | Proactive Medication Digital Twin Platform")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 26, page_str)
        self.restoreState()

def build_proposal_pdf():
    out_file = "MedGuardian_AI_Startup_Proposal.pdf"
    doc = SimpleDocTemplate(
        out_file,
        pagesize=letter,
        leftMargin=38,
        rightMargin=38,
        topMargin=48,
        bottomMargin=48
    )

    styles = getSampleStyleSheet()

    # Color Palette
    primary_color = colors.HexColor('#0f766e') # Deep Teal
    secondary_color = colors.HexColor('#0284c7') # Bright Blue
    dark_slate = colors.HexColor('#0f172a') # Slate 900
    body_color = colors.HexColor('#1e293b') # Slate 800
    muted_color = colors.HexColor('#64748b') # Slate 500
    callout_bg = colors.HexColor('#f0fdfa') # Teal 50
    callout_border = colors.HexColor('#0d9488') # Teal 600
    stat_box_bg = colors.HexColor('#f8fafc')
    header_navy = colors.HexColor('#1e293b')

    # Typography with FULL JUSTIFICATION
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16.5,
        leading=20,
        textColor=primary_color,
        spaceAfter=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=secondary_color,
        spaceAfter=3
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.8,
        textColor=muted_color,
        spaceAfter=5
    )

    h1_style = ParagraphStyle(
        'H1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=9.8,
        leading=12.5,
        textColor=primary_color,
        spaceBefore=6,
        spaceAfter=2.5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=8.4,
        leading=10.8,
        textColor=dark_slate,
        spaceBefore=4.5,
        spaceAfter=2,
        keepWithNext=True
    )

    # FULLY JUSTIFIED Body Style
    body_style = ParagraphStyle(
        'Body_Justified',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.4,
        textColor=body_color,
        alignment=TA_JUSTIFY,
        spaceAfter=3
    )

    body_bold = ParagraphStyle(
        'Body_Bold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    # FULLY JUSTIFIED Bullet Style
    bullet_style = ParagraphStyle(
        'Bullet_Justified',
        parent=body_style,
        leftIndent=8,
        bulletIndent=2,
        spaceAfter=1.8
    )

    # Table Styles
    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.8,
        leading=8.8,
        textColor=colors.white,
        alignment=TA_LEFT
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8.5,
        textColor=dark_slate,
        alignment=TA_JUSTIFY
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )

    callout_text = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.2,
        leading=9.8,
        textColor=colors.HexColor('#134e4a'),
        alignment=TA_JUSTIFY
    )

    disclaimer_style = ParagraphStyle(
        'DisclaimerText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#92400e'),
        alignment=TA_JUSTIFY
    )

    story = []

    # =========================================================================
    # PAGE 1: The Big Idea, Problem in Plain English, Solution Architecture
    # =========================================================================
    story.append(Paragraph("MedGuardian AI -- Startup & Clinical Proposal", title_style))
    story.append(Paragraph("A Student Founder's Guide to Building a Proactive Medication Digital Twin", subtitle_style))
    story.append(Paragraph(
        f"<b>Target Readers:</b> Tech Students, Student Founders & Hackathons | <b>Lead:</b> Taranpreet Kaur | <b>Generated:</b> {datetime.date.today().strftime('%B %d, %Y')}<br/>"
        f"<b>Tech Stack:</b> React 18, Django REST, Celery, Redis, ChromaDB RAG, Gemini 2.5 Flash, openFDA & NLM APIs",
        meta_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=primary_color, spaceBefore=0, spaceAfter=4))

    # 1. The Big Idea
    story.append(Paragraph("1. The Big Idea: What is MedGuardian AI?", h1_style))
    story.append(Paragraph(
        "Imagine an elderly patient managing diabetes, hypertension, and arthritis with six daily prescription drugs. "
        "What happens if their renal function declines next month and a standard daily dosage unexpectedly becomes toxic? "
        "What happens if a new doctor prescribes an antibiotic that violently clashes with their chronic heart medication? "
        "Traditional hospital software never detects these critical changes until the patient collapses and is rushed to the Emergency Department.",
        body_style
    ))
    story.append(Paragraph(
        "<b>MedGuardian AI is a 24/7 Proactive Medication Digital Twin.</b> "
        "It builds an active, synchronized digital profile of the patient in the cloud. Patients simply capture a smartphone photo of their paper prescription slip. "
        "Our multimodal vision model parses handwritten text into clean structured data, continuously tracking active medicines, documented allergies, and laboratory vitals. "
        "Whenever any patient metric shifts, background worker threads autonomously re-evaluate total regimen safety, instantly pushing real-time alerts before preventable harm occurs.",
        body_style
    ))

    # Founder Executive Box
    founder_box = [[
        Paragraph(
            "<b>Founder Executive Summary:</b><br/>"
            "• <b>Market Opportunity:</b> $4.8B Clinical Decision Support market growing at 11.2% CAGR; $182B broader Healthcare AI market.<br/>"
            "• <b>Killer Value Proposition:</b> Prevents $30,000+ ICU readmissions by catching drug toxicity before it happens.<br/>"
            "• <b>Revenue Model:</b> B2B SaaS for Hospitals ($150k/yr) + Payer Risk-Sharing ($3.50 PMPM) + Telehealth Developer APIs.<br/>"
            "• <b>Crazy Unit Economics:</b> 92.5% Gross Margin -- costs &lt; $0.005 to run an AI audit, but generates $4.00/patient/month.",
            callout_text
        )
    ]]
    t_founder_box = Table(founder_box, colWidths=[536])
    t_founder_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), callout_bg),
        ('BOX', (0,0), (-1,-1), 0.75, callout_border),
        ('PADDING', (0,0), (-1,-1), 4.5),
    ]))
    story.append(t_founder_box)
    story.append(Spacer(1, 3.5))

    # 2. The Real-World Problem
    story.append(Paragraph("2. The Real-World Problem: Why Medication Safety is Broken", h1_style))
    stats_data = [
        [
            Paragraph("<b>3+ Million Deaths/Year</b><br/>Unsafe medication practices are among the top causes of preventable death globally (WHO).", table_cell),
            Paragraph("<b>$42 Billion Annual Waste</b><br/>Hospitals and families spend billions treating completely avoidable drug-induced harm.", table_cell),
            Paragraph("<b>$30,000+ Per ICU Visit</b><br/>When a patient gets poisoned by bad drug interactions, treating them costs hospitals $30k+.", table_cell)
        ]
    ]
    t_stats = Table(stats_data, colWidths=[178, 178, 178])
    t_stats.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), stat_box_bg),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_stats)
    story.append(Spacer(1, 3))

    story.append(Paragraph("<b>Why Existing Hospital Software Fails (The 3 Critical Breakdowns):</b>", body_bold))
    story.append(Paragraph("• <b>Point-of-Prescribing Blindness:</b> Legacy systems only check safety at the exact second a doctor clicks 'Sign'. If renal function drops 3 weeks later at home, no automated review occurs.", bullet_style))
    story.append(Paragraph("• <b>Crippling Alert Fatigue:</b> Old EHRs fire annoying popups for minor interactions. Doctors receive over 100 alerts daily, leading them to override 90% to 95% of all warnings.", bullet_style))
    story.append(Paragraph("• <b>Manual Typing Bottlenecks:</b> Clinical staff spend 15 to 20 minutes manually transcribing physical prescriptions into EHRs for every patient encounter.", bullet_style))

    # 3. The Prepared Solution
    story.append(Paragraph("3. The Solution: A Proactive Medication Digital Twin", h1_style))
    story.append(Paragraph(
        "MedGuardian AI replaces manual chart audits with an autonomous, continuous safety watchdog:",
        body_style
    ))
    story.append(Paragraph("• <b>Multimodal Vision Ingestion:</b> Gemini 2.5 Flash extracts handwriting from prescription photos into structured JSON with zero manual typing.", bullet_style))
    story.append(Paragraph("• <b>Vector Guideline Search (RAG):</b> ChromaDB stores official medical books (WHO, KDIGO) as vectors, forcing the AI to quote real facts with zero hallucinations.", bullet_style))
    story.append(Paragraph("• <b>Official Federal Registries:</b> NLM RxNav translates brand names to generic IDs, while openFDA supplies real-time boxed warnings.", bullet_style))
    story.append(Paragraph("• <b>Asynchronous Background Queue:</b> Celery & Redis audit patient safety 24/7 without slowing down or freezing the web application.", bullet_style))
    story.append(Paragraph("• <b>Real-Time Push Alerts:</b> Pushes instant Server-Sent Events (SSE) alerts only when risk escalates from Safe to Severe.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: Code Translation Table, Clinician Protocol, Why MedGuardian Must Be a Startup
    # =========================================================================
    story.append(Paragraph("4. Translating Technical Code into Plain-English Roles", h1_style))
    tech_table_data = [
        [Paragraph("Codebase Technology", table_header), Paragraph("Plain-English Analogy", table_header), Paragraph("What It Actually Does in the App", table_header)],
        [
            Paragraph("<b>Gemini 2.5 Flash Vision</b>", table_cell_bold),
            Paragraph("The Super-Fast Scribe", table_cell),
            Paragraph("Reads messy doctor handwriting on paper prescriptions and converts it to clean JSON in under 1 second.", table_cell)
        ],
        [
            Paragraph("<b>ChromaDB Vector RAG</b>", table_cell_bold),
            Paragraph("Instant Medical Librarian", table_cell),
            Paragraph("Searches official medical guideline books stored as vectors, ensuring AI responses quote verified literature without hallucinating.", table_cell)
        ],
        [
            Paragraph("<b>NLM RxNav & openFDA APIs</b>", table_cell_bold),
            Paragraph("Official Drug Encyclopedia", table_cell),
            Paragraph("Queries US federal databases for chemical drug interactions, dosage limits, and manufacturer black-box warnings.", table_cell)
        ],
        [
            Paragraph("<b>Celery + Redis Queue</b>", table_cell_bold),
            Paragraph("24/7 Watchdog Resident", table_cell),
            Paragraph("Runs heavy safety checks in the background. Redis 10s debounce lock collapses rapid clicks into 1 single evaluation.", table_cell)
        ],
        [
            Paragraph("<b>Gemini 2.5 Flash Synthesizer</b>", table_cell_bold),
            Paragraph("Clinical Pharmacologist", table_cell),
            Paragraph("Combines lab metrics, drug interaction tables, and guideline excerpts into an explainable safety grade and summary.", table_cell)
        ],
        [
            Paragraph("<b>ReportLab PDF Engine</b>", table_cell_bold),
            Paragraph("Automated Dossier Builder", table_cell),
            Paragraph("Generates simple 1-page guides for patients and high-density 2-page clinical dossiers for doctor medical charts.", table_cell)
        ]
    ]
    t_tech = Table(tech_table_data, colWidths=[125, 110, 301])
    t_tech.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0,0), (-1,-1), 3.2),
    ]))
    story.append(t_tech)
    story.append(Spacer(1, 4))

    # 5. Clinician-in-the-Loop Protocol
    story.append(Paragraph("5. Clinician-in-the-Loop: Zero Legal Liability for Developers", h1_style))
    story.append(Paragraph(
        "MedGuardian AI is strictly engineered as an <b>Assistant, not an Autonomous Doctor</b>. This keeps developers legally shielded:",
        body_style
    ))
    story.append(Paragraph("1. <b>Pending Verification Queue:</b> Ingested medications enter a 'Pending Review' holding state and do not join active charts until verified by a physician.", bullet_style))
    story.append(Paragraph("2. <b>Doctor Override Power:</b> Clinicians can override alerts with a 1-click documented clinical rationale, which is cryptographically logged for audit compliance.", bullet_style))
    story.append(Paragraph("3. <b>Strict Zero-Hallucination Rule:</b> If guidelines are absent in ChromaDB, the AI states: <i>'Insufficient clinical evidence to answer safely'</i>, blocking fake advice.", bullet_style))

    story.append(Spacer(1, 4))

    # 6. WHY THIS PROJECT NEEDS TO BE A STARTUP (NEW DEDICATED SECTION)
    story.append(Paragraph("6. Why MedGuardian AI MUST Be a Startup (Not Just an Academic Tool)", h1_style))
    story.append(Paragraph(
        "Many student projects remain locked inside university repositories. MedGuardian AI is specifically designed as a high-growth startup for five reasons:",
        body_style
    ))
    story.append(Paragraph("• <b>The Neutral Cross-Hospital Bridge:</b> Patients visit multiple specialists, retail pharmacies (CVS/Walgreens), and telehealth clinics. A single hospital EHR (Epic/Cerner) will NEVER build software that syncs with rival clinics. Only an independent startup can serve as the universal, patient-centric safety layer.", bullet_style))
    story.append(Paragraph("• <b>Legacy Incumbents Are Too Slow:</b> Giant EHR vendors profit from expensive server licenses and vendor lock-in. They have zero incentive to build fast, lightweight, multimodal AI tools that reduce hospital visits. An agile startup can build and ship 10x faster.", bullet_style))
    story.append(Paragraph("• <b>The Telehealth & E-Pharmacy Boom:</b> Modern virtual clinics (Ro, Hims, Teladoc, Amazon Clinic) are rapidly expanding. They urgently need lightweight, developer-friendly medication safety APIs that traditional hospital EHRs cannot supply.", bullet_style))
    story.append(Paragraph("• <b>Venture-Scale Economics (92%+ Gross Margin):</b> With marginal server costs under half a cent (<$0.005 per audit) and $4.00/patient monthly SaaS revenue, this product generates elite venture-capital profit margins that can scale nationwide.", bullet_style))
    story.append(Paragraph("• <b>From Research Paper to Saving Real Lives:</b> Academic research papers do not save lives in emergency rooms. Building a venture-backed startup ensures 24/7 reliability, continuous product development, and massive clinical adoption.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: Market Feasibility, Customer vs User, Why Now Tech Wave
    # =========================================================================
    story.append(Paragraph("7. Market Feasibility & Macroeconomic Opportunity", h1_style))
    story.append(Paragraph(
        "Healthcare AI is experiencing unprecedented expansion driven by hospital penalties and demographic shifts:",
        body_style
    ))

    mkt_data = [
        [
            Paragraph("<b>Total Addressable Market (TAM)</b><br/><b>$182.4 Billion (2030)</b><br/>Global AI in Healthcare, Telehealth, and Remote Patient Monitoring expanding at 38.4% CAGR.", table_cell),
            Paragraph("<b>Serviceable Addressable (SAM)</b><br/><b>$4.8 Billion (2028)</b><br/>Dedicated Clinical Decision Support Software (CDSS) & Medication Therapy Management (MTM).", table_cell),
            Paragraph("<b>Serviceable Obtainable (SOM)</b><br/><b>$420 Million (Year 3)</b><br/>Targeting 800 US Telehealth startups, 450 Medicare ACO groups, and 2,500 assisted living homes.", table_cell)
        ]
    ]
    t_mkt = Table(mkt_data, colWidths=[178, 178, 178])
    t_mkt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0fdf4')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#86efac')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#bbf7d0')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_mkt)
    story.append(Spacer(1, 3))

    story.append(Paragraph("<b>The 3 Big Macro Drivers:</b>", body_bold))
    story.append(Paragraph("• <b>Hospital Fines (Value-Based Care):</b> Under the US CMS Hospital Readmissions Reduction Program (HRRP), hospitals lose up to 3% of Medicare reimbursements for excess 30-day readmissions. Preventing adverse drug events protects hospital bottom lines directly.", bullet_style))
    story.append(Paragraph("• <b>The Silver Tsunami:</b> Over 42% of adults over 65 take 5 or more daily prescription drugs, creating an unmanageable review burden for doctors.", bullet_style))
    story.append(Paragraph("• <b>FDA Non-Device CDS Exemption:</b> Under Section 3060(a) of the 21st Century Cures Act, explainable CDS tools are exempt from costly FDA medical device trials.", bullet_style))

    story.append(Spacer(1, 4))

    # 8. Customer vs User Table
    story.append(Paragraph("8. Customer vs. User: Who Pays vs. Who Uses?", h1_style))
    story.append(Paragraph(
        "In B2B healthcare startups, the <b>Customer (who pays)</b> is distinct from the <b>User (who operates daily)</b>:",
        body_style
    ))

    stakeholder_table_data = [
        [Paragraph("Stakeholder Group", table_header), Paragraph("Why They Love It (Value Proposition)", table_header), Paragraph("How We Make Money (Monetization)", table_header)],
        [
            Paragraph("<b>Hospitals & Health Networks (Customer)</b>", table_cell_bold),
            Paragraph("Avoids costly 30-day readmission fines; lowers malpractice risk; makes clinical pharmacists 4x faster.", table_cell),
            Paragraph("Enterprise Annual SaaS ($150k - $450k ARR per hospital network).", table_cell)
        ],
        [
            Paragraph("<b>Insurance & ACOs (Customer)</b>", table_cell_bold),
            Paragraph("Saves millions on unneeded $30,000+ ICU hospitalizations from drug toxicity.", table_cell),
            Paragraph("$2.50 - $5.00 Per-Member-Per-Month (PMPM) + 15% Shared Savings fee.", table_cell)
        ],
        [
            Paragraph("<b>Telehealth Startups (Customer)</b>", table_cell_bold),
            Paragraph("Plug-and-play safety check API for virtual doctor appointments and online pharmacy apps.", table_cell),
            Paragraph("Developer API ($0.10 / prescription scan, $0.05 / safety check).", table_cell)
        ],
        [
            Paragraph("<b>Assisted Living Homes (Customer)</b>", table_cell_bold),
            Paragraph("Automates daily medication safety logs for 50-200 elderly residents.", table_cell),
            Paragraph("Monthly Facility Plan ($1,500 - $4,000 / facility / month).", table_cell)
        ],
        [
            Paragraph("<b>Doctors & Pharmacists (User)</b>", table_cell_bold),
            Paragraph("Eliminates 90% useless popup fatigue; gives 1-click clinical dossiers and source evidence.", table_cell),
            Paragraph("Included in hospital enterprise software license.", table_cell)
        ],
        [
            Paragraph("<b>Patients & Caregivers (User/Consumer)</b>", table_cell_bold),
            Paragraph("Instant phone scan of paper prescriptions; plain-language alerts; 24/7 AI chat helper.", table_cell),
            Paragraph("Freemium Mobile App ($9.99/month Eldercare Family Plan).", table_cell)
        ]
    ]
    t_stakeholders = Table(stakeholder_table_data, colWidths=[130, 205, 201])
    t_stakeholders.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), header_navy),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0,0), (-1,-1), 3.0),
    ]))
    story.append(t_stakeholders)
    story.append(Spacer(1, 4))

    # 9. Why Now Tech Wave
    story.append(Paragraph("9. The 'Why Now?' Technology Inflection Point", h1_style))
    story.append(Paragraph("• <b>Vision AI is Finally Here:</b> Gemini 2.5 Flash parses handwritten prescription slips in 800ms with high accuracy at a fraction of a cent per image.", bullet_style))
    story.append(Paragraph("• <b>RAG Solves Hallucinations:</b> ChromaDB forces the model to only answer using real medical books, making AI safe for healthcare.", bullet_style))
    story.append(Paragraph("• <b>SMART-on-FHIR APIs:</b> US federal law requires hospitals to open their data APIs, letting MedGuardian AI plug into Epic & Cerner seamlessly.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: Unit Economics, Strategic Moats, Roadmap, Legal Rules, Pitch
    # =========================================================================
    story.append(Paragraph("10. Exceptional Unit Economics & Scalability (92%+ Gross Margin)", h1_style))
    unit_econ_data = [
        [Paragraph("Metric", table_header), Paragraph("Value", table_header), Paragraph("Why This Matters for Investors", table_header)],
        [Paragraph("Server / AI Cost per Audit", table_cell_bold), Paragraph("< $0.005", table_cell), Paragraph("Local ChromaDB caching + Gemini 2.5 Flash token efficiency keeps cost near zero.", table_cell)],
        [Paragraph("Revenue per Patient / Month", table_cell_bold), Paragraph("$4.00", table_cell), Paragraph("Standard B2B SaaS pricing paid by hospitals and insurance programs.", table_cell)],
        [Paragraph("Software Gross Margin", table_cell_bold), Paragraph("92.5%", table_cell), Paragraph("Elite SaaS margin profile -- almost all revenue turns directly into gross profit.", table_cell)],
        [Paragraph("Hospital Contract Value (LTV)", table_cell_bold), Paragraph("$450,000", table_cell), Paragraph("3-year enterprise contract value with low hospital customer churn.", table_cell)],
        [Paragraph("Customer Acquisition Cost (CAC)", table_cell_bold), Paragraph("$35,000", table_cell), Paragraph("Sales cost to close one mid-size hospital network.", table_cell)],
        [Paragraph("LTV / CAC Ratio", table_cell_bold), Paragraph("> 12 : 1", table_cell), Paragraph("Venture capital gold standard (anything above 3:1 is considered great).", table_cell)]
    ]
    t_econ = Table(unit_econ_data, colWidths=[140, 75, 321])
    t_econ.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0,0), (-1,-1), 2.8),
    ]))
    story.append(t_econ)
    story.append(Spacer(1, 4))

    # 11. 4 Moats
    story.append(Paragraph("11. Our 4 Competitive Moats (Why We Win)", h1_style))
    story.append(Paragraph("• <b>24/7 Digital Twin vs. Static Checkers:</b> Epic & Cerner only check pills when a doctor is typing. MedGuardian AI monitors 24/7 at home when vitals change.", bullet_style))
    story.append(Paragraph("• <b>Worsening-Only Alerts:</b> Suppresses repetitive popups and only alerts when safety jumps (e.g., Safe &rarr; Severe), ending alert fatigue.", bullet_style))
    story.append(Paragraph("• <b>Clinician-in-the-Loop Shield:</b> Built-in approval queue and override audit logs protect the company from medical malpractice liability.", bullet_style))
    story.append(Paragraph("• <b>Offline Local Fallback:</b> Works seamlessly in clinics with poor internet using local rule engines and cached vector stores.", bullet_style))

    # 12. Execution Roadmap
    story.append(Paragraph("12. The 3-Year Founder Execution Roadmap", h1_style))
    story.append(Paragraph("• <b>Phase 1 (Months 1-12) -- Beachhead:</b> Launch developer APIs for 15 telehealth platforms and pilot in 5 senior care clinics. Target: 25k users, $400k ARR.", bullet_style))
    story.append(Paragraph("• <b>Phase 2 (Months 12-24) -- Expansion:</b> Sign shared-savings contracts with 10 Medicare ACO insurance plans and publish clinical study. Target: 150k users, $2.5M ARR.", bullet_style))
    story.append(Paragraph("• <b>Phase 3 (Months 24-36) -- Enterprise Scale:</b> Launch 1-click app on the Epic App Orchard and Oracle Health Store. Target: 750k+ users, $12M+ ARR.", bullet_style))

    # 13. Legal & Privacy Rules
    story.append(Paragraph("13. Legal, FDA & Privacy Rules (Made Simple)", h1_style))
    story.append(Paragraph(
        "• <b>FDA Non-Device Clearance:</b> Under Section 3060(a) of the 21st Century Cures Act, clinical decision support software does NOT require heavy medical device approval if it explains its rationale and requires a human doctor's sign-off.<br/>"
        "• <b>HIPAA / Patient Privacy:</b> Full database-level patient isolation, bank-grade encryption (TLS 1.3 & AES-256), and zero patient health data shared to train public AI models.<br/>"
        "• <b>Tamper-Proof Audit Trail:</b> Every alert generated, reviewed, or overridden is permanently logged with timestamps for hospital legal defense.",
        body_style
    ))

    # 14. Conclusion & Pitch
    story.append(Paragraph("14. Conclusion & The 30-Second Hackathon / Investor Pitch", h1_style))
    story.append(Paragraph(
        "<i>\"3 million people die every year from preventable medication mistakes, wasting $42 Billion. "
        "Current hospital software fails because it only checks pills during brief office visits and bombards doctors with useless popups. "
        "MedGuardian AI is a 24/7 Medication Digital Twin that reads paper prescriptions with vision AI, continuously monitors patient vitals in the background, "
        "and pushes real-time alerts only when genuine danger escalates. With a $4.8B market, 92% profit margins, and zero FDA red tape, "
        "MedGuardian AI is the proactive safety net for modern digital health.\"</i>",
        body_style
    ))
    story.append(Spacer(1, 3.5))

    # Disclaimer Box
    disclaimer_box = [[
        Paragraph(
            "<b>IMPORTANT REGULATORY & CLINICAL NOTICE:</b><br/>"
            "MedGuardian AI is an educational clinical decision support (CDS) tool designed to assist healthcare professionals with medication safety auditing. "
            "It is not an autonomous diagnostic device, does not formulate independent medical treatment plans, and does not replace the professional judgment of a licensed physician or pharmacist. "
            "The attending clinician remains the final and exclusive medical authority.",
            disclaimer_style
        )
    ]]
    t_disclaimer = Table(disclaimer_box, colWidths=[536])
    t_disclaimer.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fffbeb')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#f59e0b')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_disclaimer)

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {out_file}")

    # Try copying to other names if not locked
    for alt_name in ["clinician_proposal.pdf", "MedGuardian_Startup_Proposal.pdf"]:
        try:
            import shutil
            shutil.copyfile(out_file, alt_name)
            print(f"Successfully updated {alt_name}")
        except Exception as e:
            print(f"Note: {alt_name} could not be updated directly (file open in viewer): {e}")

if __name__ == "__main__":
    build_proposal_pdf()
