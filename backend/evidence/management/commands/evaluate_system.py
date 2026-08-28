import os
import json
import time
import logging
from datetime import datetime
import numpy as np
import pandas as pd
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Orchestrate end-to-end clinical validation by running risk engine evaluation and RAG retrieval evaluation."

    def add_arguments(self, parser):
        parser.add_argument('--offline', action='store_true', help="Force offline mode for accuracy evaluation")

    def handle(self, *args, **options):
        offline = options['offline']
        self.stdout.write("=" * 60)
        self.stdout.write("   MedGuardian AI — Starting End-to-End Validation Suite")
        self.stdout.write("=" * 60)

        reports_dir = os.path.join(settings.BASE_DIR, 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        # 1. Execute Module 1: Risk Engine Accuracy Evaluation
        self.stdout.write("\n>>> [1/2] Running Risk Engine Accuracy Evaluation...")
        acc_start = time.perf_counter()
        call_command('evaluate_accuracy', offline=offline)
        acc_duration = time.perf_counter() - acc_start
        self.stdout.write(f"Accuracy evaluation completed in {acc_duration:.2f} seconds.")

        # 2. Execute Module 3: RAG Retrieval Evaluation
        self.stdout.write("\n>>> [2/2] Running RAG Retrieval Evaluation...")
        rag_start = time.perf_counter()
        call_command('evaluate_rag')
        rag_duration = time.perf_counter() - rag_start
        self.stdout.write(f"RAG evaluation completed in {rag_duration:.2f} seconds.")

        # 3. Read generated metrics
        acc_metrics_path = os.path.join(reports_dir, 'metrics.json')
        rag_metrics_path = os.path.join(reports_dir, 'rag_metrics.json')

        acc_metrics = {}
        if os.path.exists(acc_metrics_path):
            with open(acc_metrics_path, 'r', encoding='utf-8') as f:
                acc_metrics = json.load(f)

        rag_metrics = {}
        if os.path.exists(rag_metrics_path):
            with open(rag_metrics_path, 'r', encoding='utf-8') as f:
                rag_metrics = json.load(f)

        # 4. Generate Combined Metrics JSON
        e2e_metrics = {
            "validation_timestamp": datetime.now().isoformat(),
            "offline_mode": offline,
            "risk_engine": acc_metrics,
            "rag_retrieval": rag_metrics
        }
        e2e_json_path = os.path.join(reports_dir, 'system_metrics.json')
        with open(e2e_json_path, 'w', encoding='utf-8') as f:
            json.dump(e2e_metrics, f, indent=2)

        # 5. Print Unified Dashboard
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("      MedGuardian AI — E2E Clinical Validation Summary")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Timestamp               : {e2e_metrics['validation_timestamp']}")
        self.stdout.write(f"Evaluation Mode         : {'OFFLINE (Rules Fallback)' if offline else 'ONLINE (Gemini API)'}")
        self.stdout.write("-" * 60)
        self.stdout.write(" [Risk Engine Performance]")
        self.stdout.write(f"   - Tested Patients    : {acc_metrics.get('total_cases', 0)}")
        self.stdout.write(f"   - Accuracy           : {acc_metrics.get('accuracy', 0.0):.2f}%")
        self.stdout.write(f"   - Balanced Accuracy  : {acc_metrics.get('balanced_accuracy', 0.0):.2f}%")
        self.stdout.write(f"   - Specificity        : {acc_metrics.get('specificity_average', 0.0):.2f}%")
        self.stdout.write(f"   - F1 Score           : {acc_metrics.get('f1_score_macro', 0.0):.2f}%")
        self.stdout.write(f"   - Avg Response Time  : {acc_metrics.get('average_latency_ms', 0.0):.2f} ms")
        self.stdout.write("-" * 60)
        self.stdout.write(" [RAG Retrieval Performance]")
        self.stdout.write(f"   - Tested Queries     : {rag_metrics.get('total_queries_evaluated', 0)}")
        self.stdout.write(f"   - Precision@5        : {rag_metrics.get('precision_at_k', 0.0):.2f}%")
        self.stdout.write(f"   - Recall@5           : {rag_metrics.get('recall_at_k', 0.0):.2f}%")
        self.stdout.write(f"   - MRR                : {rag_metrics.get('mean_reciprocal_rank', 0.0):.4f}")
        self.stdout.write(f"   - nDCG@5             : {rag_metrics.get('ndcg_at_k', 0.0):.4f}")
        self.stdout.write(f"   - Avg Search Latency : {rag_metrics.get('average_retrieval_time_ms', 0.0):.2f} ms")
        self.stdout.write("=" * 60 + "\n")

        # 6. Generate E2E PDF Report
        pdf_path = os.path.join(reports_dir, 'system_validation_report.pdf')
        self.generate_e2e_pdf(pdf_path, e2e_metrics, reports_dir)

        self.stdout.write(self.style.SUCCESS(f"Saved end-to-end reports to backend/reports/ folder:"))
        self.style.SUCCESS(self.stdout.write(f" - Unified JSON Metrics : backend/reports/system_metrics.json"))
        self.style.SUCCESS(self.stdout.write(f" - Unified PDF Report   : backend/reports/system_validation_report.pdf"))

    def generate_e2e_pdf(self, pdf_path, e2e_metrics, reports_dir):
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=colors.HexColor('#1A365D'),
            spaceAfter=15
        )

        subtitle_style = ParagraphStyle(
            'DocSub',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=10,
            textColor=colors.HexColor('#4A5568'),
            spaceAfter=15
        )

        section_heading = ParagraphStyle(
            'SecHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=colors.HexColor('#2C5282'),
            spaceBefore=12,
            spaceAfter=8
        )

        cell_text = ParagraphStyle(
            'CellText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=11
        )

        story = []

        # Header
        story.append(Paragraph("MedGuardian AI — E2E Clinical Validation Report", title_style))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Offline Mode: {e2e_metrics['offline_mode']}", subtitle_style))
        story.append(Spacer(1, 10))

        # Risk Engine Table
        acc = e2e_metrics["risk_engine"]
        story.append(Paragraph("1. Risk Engine Safety Assessment Performance", section_heading))
        risk_data = [
            [Paragraph("<b>Performance Metric</b>", cell_text), Paragraph("<b>Value</b>", cell_text)],
            [Paragraph("Total Patient Cases Evaluated", cell_text), f"{acc.get('total_cases', 0)}"],
            [Paragraph("Classification Accuracy", cell_text), f"{acc.get('accuracy', 0.0):.2f}%"],
            [Paragraph("Balanced Accuracy", cell_text), f"{acc.get('balanced_accuracy', 0.0):.2f}%"],
            [Paragraph("Precision (Macro Avg)", cell_text), f"{acc.get('precision_macro', 0.0):.2f}%"],
            [Paragraph("Recall/Sensitivity (Macro Avg)", cell_text), f"{acc.get('recall_macro', 0.0):.2f}%"],
            [Paragraph("Specificity (Macro Avg)", cell_text), f"{acc.get('specificity_average', 0.0):.2f}%"],
            [Paragraph("F1 Score (Macro Avg)", cell_text), f"{acc.get('f1_score_macro', 0.0):.2f}%"],
            [Paragraph("ROC-AUC Score (Macro Avg)", cell_text), f"{acc.get('roc_auc', 0.0):.2f}"],
            [Paragraph("Average Execution Latency", cell_text), f"{acc.get('average_latency_ms', 0.0):.2f} ms"]
        ]
        risk_table = Table(risk_data, colWidths=[300, 240])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EDF2F7')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(risk_table)
        story.append(Spacer(1, 15))

        # RAG Retrieval Table
        rag = e2e_metrics["rag_retrieval"]
        story.append(Paragraph("2. RAG Retrieval Performance (K=5)", section_heading))
        rag_data = [
            [Paragraph("<b>Performance Metric</b>", cell_text), Paragraph("<b>Value</b>", cell_text)],
            [Paragraph("Total Clinical Queries Evaluated", cell_text), f"{rag.get('total_queries_evaluated', 0)}"],
            [Paragraph("Precision@5", cell_text), f"{rag.get('precision_at_k', 0.0):.2f}%"],
            [Paragraph("Recall@5", cell_text), f"{rag.get('recall_at_k', 0.0):.2f}%"],
            [Paragraph("Mean Reciprocal Rank (MRR)", cell_text), f"{rag.get('mean_reciprocal_rank', 0.0):.4f}"],
            [Paragraph("nDCG@5", cell_text), f"{rag.get('ndcg_at_k', 0.0):.4f}"],
            [Paragraph("Average Search Latency", cell_text), f"{rag.get('average_retrieval_time_ms', 0.0):.2f} ms"]
        ]
        rag_table = Table(rag_data, colWidths=[300, 240])
        rag_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EDF2F7')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(rag_table)
        story.append(Spacer(1, 15))

        # Embed validation figures side-by-side
        cm_img_path = os.path.join(reports_dir, "confusion_matrix.png")
        roc_img_path = os.path.join(reports_dir, "roc_curve.png")
        
        if os.path.exists(cm_img_path) and os.path.exists(roc_img_path):
            story.append(Paragraph("3. Risk Engine Diagnostic Charts", section_heading))
            img_table_data = [
                [
                    RLImage(cm_img_path, width=250, height=200),
                    RLImage(roc_img_path, width=250, height=200)
                ]
            ]
            img_table = Table(img_table_data, colWidths=[270, 270])
            img_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(img_table)

        # Build document
        doc.build(story)
