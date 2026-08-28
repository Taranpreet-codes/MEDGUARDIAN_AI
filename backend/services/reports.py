import io
import datetime
import xml.sax.saxutils as saxutils
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from patients.models import PatientProfile, MedicationCabinet, InteractionLog


def _esc(val) -> str:
    """
    Safely escapes XML/HTML-sensitive characters (&, <, >) for ReportLab Paragraph markup.
    Converts None/numeric/date types safely to string representations.
    Preserves verbatim clinical text and does not drop any characters or words.
    """
    if val is None:
        return ""
    return saxutils.escape(str(val))


class ReportService:
    @staticmethod
    def generate_patient_report(profile: PatientProfile) -> bytes:
        """Generates a patient-friendly plain-language safety and cabinet PDF report."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
        )
        
        styles = getSampleStyleSheet()
        
        # Custom Styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=22,
            textColor=colors.HexColor('#0f766e'), # Teal 700
            spaceAfter=15
        )
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#0d9488'), # Teal 600
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#334155') # Slate 700
        )
        disclaimer_style = ParagraphStyle(
            'DisclaimerStyle',
            parent=styles['Normal'],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#b45309') # Amber 700
        )

        elements = []

        # Title / Header
        elements.append(Paragraph("MedGuardian AI — Patient Safety Summary", title_style))
        elements.append(Paragraph(f"Generated on: {datetime.date.today().strftime('%B %d, %Y')}", body_style))
        elements.append(Paragraph(f"Patient Name: {_esc(profile.user.username)}", body_style))
        elements.append(Spacer(1, 15))

        # Profile Summary
        elements.append(Paragraph("Your Health Profile Twin", section_style))
        profile_data = [
            [Paragraph("<b>Age:</b>", body_style), Paragraph(_esc(profile.age), body_style),
             Paragraph("<b>Gender:</b>", body_style), Paragraph(_esc(profile.get_gender_display()), body_style)],
            [Paragraph("<b>Pregnancy Status:</b>", body_style), Paragraph("Pregnant" if profile.pregnancy_status else "Not Pregnant", body_style),
             Paragraph("<b>Documented Allergies:</b>", body_style), Paragraph(", ".join(_esc(a) for a in profile.allergies) if profile.allergies else "None", body_style)],
            [Paragraph("<b>Chronic Conditions:</b>", body_style), Paragraph(", ".join(_esc(d) for d in profile.chronic_diseases) if profile.chronic_diseases else "None", body_style),
             "", ""]
        ]
        t_profile = Table(profile_data, colWidths=[120, 140, 120, 140])
        t_profile.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LINEBELOW', (0,-1), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(t_profile)
        elements.append(Spacer(1, 15))

        # Medication Cabinet
        elements.append(Paragraph("Your Active Medication Cabinet", section_style))
        meds = MedicationCabinet.objects.filter(patient=profile, is_active=True)
        
        if not meds.exists():
            elements.append(Paragraph("<i>No active medications logged in your cabinet.</i>", body_style))
        else:
            med_table_data = [[
                Paragraph("<b>Medication</b>", body_style),
                Paragraph("<b>Dosage</b>", body_style),
                Paragraph("<b>Frequency</b>", body_style),
                Paragraph("<b>Start Date</b>", body_style)
            ]]
            for m in meds:
                med_table_data.append([
                    Paragraph(_esc(m.name), body_style),
                    Paragraph(_esc(m.dosage), body_style),
                    Paragraph(_esc(m.frequency), body_style),
                    Paragraph(m.start_date.strftime('%Y-%m-%d') if m.start_date else "", body_style)
                ])
            t_meds = Table(med_table_data, colWidths=[150, 100, 150, 120])
            t_meds.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('PADDING', (0,0), (-1,-1), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            elements.append(t_meds)
        
        elements.append(Spacer(1, 20))

        # Safety Guidelines / Risks
        elements.append(Paragraph("Active Safety Cautions & Care Guidance", section_style))
        latest_log = InteractionLog.objects.filter(patient=profile).order_by('-created_at')
        if latest_log.exists():
            log = latest_log.first()
            risk_score = log.risk_score
            warnings = log.details.get("interactions", [])
            
            elements.append(Paragraph(f"<b>Overall Safety Profile:</b> {_esc(risk_score)} Risk Level", body_style))
            elements.append(Spacer(1, 6))
            
            if not warnings:
                elements.append(Paragraph("No severe conflicts detected between your conditions or medications at this time.", body_style))
            else:
                for w in warnings:
                    elements.append(Paragraph(
                        f"• <b>{_esc(w.get('drug_involved', 'General Alert'))}</b> ({_esc(w.get('severity', 'Low'))}): {_esc(w.get('description', ''))}", 
                        body_style
                    ))
                    elements.append(Spacer(1, 4))
        else:
            elements.append(Paragraph("<i>Safety audit has not been executed yet. Run audit in portal dashboard.</i>", body_style))
            
        elements.append(Spacer(1, 25))

        # Disclaimer
        elements.append(Paragraph("<b>Clinical Safety Notice & Disclaimer</b>", body_style))
        elements.append(Spacer(1, 3))
        elements.append(Paragraph(
            "MedGuardian AI is an educational clinical decision support tool designed to assist with medication safety. "
            "It is NOT a diagnostic device, does not provide medical treatment, and should never replace professional consultation "
            "with a qualified pharmacist or physician. Always cross-reference instructions with physical pharmacy labels.",
            disclaimer_style
        ))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def generate_clinician_report(profile: PatientProfile) -> bytes:
        """Generates a high-density clinical summary PDF for doctors/pharmacists."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
        )
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'ClinTitleStyle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#0f172a'), # Slate 900
            spaceAfter=10
        )
        section_style = ParagraphStyle(
            'ClinSectionStyle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#0f766e'), # Teal 700
            spaceBefore=10,
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            'ClinBodyStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1e293b') # Slate 800
        )
        disclaimer_style = ParagraphStyle(
            'ClinDisclaimerStyle',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#475569') # Slate 600
        )

        elements = []

        # Title
        elements.append(Paragraph("MedGuardian AI — Clinician Safety Dossier", title_style))
        elements.append(Paragraph(f"Date: {datetime.date.today().strftime('%Y-%m-%d')} | Subject ID: PHI-TWIN-{profile.id}", body_style))
        elements.append(Spacer(1, 10))

        # Demographic & Lab Data
        elements.append(Paragraph("Demographics & Lab Markers (eGFR/Creatinine)", section_style))
        lab_data = [
            [Paragraph("<b>Demographics:</b>", body_style), Paragraph(f"Age {_esc(profile.age)} • Gender {_esc(profile.gender)} • Pregnancy: {profile.pregnancy_status}", body_style)],
            [Paragraph("<b>Creatinine (mg/dL):</b>", body_style), Paragraph(_esc(profile.creatinine) if profile.creatinine else "Not Logged", body_style)],
            [Paragraph("<b>eGFR (mL/min/1.73m²):</b>", body_style), Paragraph(_esc(profile.egfr) if profile.egfr else "Not Logged", body_style)],
            [Paragraph("<b>Allergies:</b>", body_style), Paragraph(", ".join(_esc(a) for a in profile.allergies) if profile.allergies else "None documented", body_style)],
            [Paragraph("<b>Chronic Conditions:</b>", body_style), Paragraph(", ".join(_esc(d) for d in profile.chronic_diseases) if profile.chronic_diseases else "None documented", body_style)]
        ]
        t_labs = Table(lab_data, colWidths=[150, 370])
        t_labs.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
            ('PADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(t_labs)
        elements.append(Spacer(1, 10))

        # Active Medications
        elements.append(Paragraph("Active Medications Cabinet", section_style))
        meds = MedicationCabinet.objects.filter(patient=profile, is_active=True)
        if not meds.exists():
            elements.append(Paragraph("No active medications found in patient profile.", body_style))
        else:
            med_table_data = [[
                Paragraph("<b>Active Drug</b>", body_style),
                Paragraph("<b>Strength</b>", body_style),
                Paragraph("<b>Frequency</b>", body_style),
                Paragraph("<b>Start Date</b>", body_style)
            ]]
            for m in meds:
                med_table_data.append([
                    Paragraph(_esc(m.name), body_style),
                    Paragraph(_esc(m.dosage), body_style),
                    Paragraph(_esc(m.frequency), body_style),
                    Paragraph(m.start_date.strftime('%Y-%m-%d') if m.start_date else "", body_style)
                ])
            t_meds = Table(med_table_data, colWidths=[150, 100, 150, 120])
            t_meds.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('PADDING', (0,0), (-1,-1), 4),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ]))
            elements.append(t_meds)

        elements.append(Spacer(1, 10))

        # Risk Analysis
        elements.append(Paragraph("Evaluator Risk Analysis Details", section_style))
        latest_log = InteractionLog.objects.filter(patient=profile).order_by('-created_at')
        if latest_log.exists():
            log = latest_log.first()
            risk_score = log.risk_score
            warnings = log.details.get("interactions", [])
            references = log.details.get("evidence_references", [])
            notes = log.details.get("clinician_notes", "")

            elements.append(Paragraph(f"<b>Audit Verdict:</b> {_esc(risk_score)} Risk Tier (Generated {log.created_at.strftime('%Y-%m-%d')})", body_style))
            elements.append(Spacer(1, 4))
            
            if warnings:
                warning_data = [[
                    Paragraph("<b>Drug(s)</b>", body_style),
                    Paragraph("<b>Severity</b>", body_style),
                    Paragraph("<b>Warning/Mechanism</b>", body_style)
                ]]
                for w in warnings:
                    warning_data.append([
                        Paragraph(_esc(w.get('drug_involved', '')), body_style),
                        Paragraph(_esc(w.get('severity', '')), body_style),
                        Paragraph(_esc(w.get('description', '')), body_style)
                    ])
                t_warn = Table(warning_data, colWidths=[120, 70, 330])
                t_warn.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#fee2e2') if risk_score == 'Severe' else colors.HexColor('#fef3c7')),
                    ('PADDING', (0,0), (-1,-1), 5),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ]))
                elements.append(t_warn)
            else:
                elements.append(Paragraph("No active alerts logged.", body_style))

            if notes:
                elements.append(Spacer(1, 6))
                elements.append(Paragraph(f"<b>Clinician Evaluation Notes:</b>", body_style))
                elements.append(Paragraph(_esc(notes), body_style))

            if references:
                elements.append(Spacer(1, 6))
                elements.append(Paragraph(f"<b>Indexed References consulted:</b>", body_style))
                elements.append(Paragraph(", ".join(_esc(r) for r in references), body_style))
        else:
            elements.append(Paragraph("Safety check not run.", body_style))

        elements.append(Spacer(1, 20))

        # Disclaimer
        elements.append(Paragraph("<b>Clinical Verification Required</b>", body_style))
        elements.append(Paragraph(
            "MedGuardian AI acts as a reactive medication decision support adapter. All warning signals must be clinically verified "
            "against primary sources. This report is for professional reference only and is not a clinical directive.",
            disclaimer_style
        ))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
