import os
import json
import time
import csv
import logging
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Set non-interactive backend before importing pyplot
import matplotlib.pyplot as plt

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    accuracy_score,
    precision_recall_fscore_support
)
from sklearn.preprocessing import label_binarize
from sklearn.metrics import roc_auc_score, roc_curve

from patients.models import PatientProfile, MedicationCabinet
from services.risk_engine import RiskEngine

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)

# Normalize risk labels for mapping
RISK_LABELS = ['SAFE', 'LOW', 'MODERATE', 'SEVERE']

def normalize_risk(risk_str: str) -> str:
    r = risk_str.upper().strip()
    if r in ('HIGH', 'SEVERE'):
        return 'SEVERE'
    if r in ('MODERATE',):
        return 'MODERATE'
    if r in ('LOW',):
        return 'LOW'
    return 'SAFE'

class Command(BaseCommand):
    help = "Run clinical validation benchmark suite, compute accuracy metrics, and generate clinical reports."

    def add_arguments(self, parser):
        parser.add_argument('--dataset', type=str, default='clinical_benchmark.json', help="Benchmark filename in data/")
        parser.add_argument('--limit', type=int, default=0, help="Limit number of profiles evaluated (0 for all)")
        parser.add_argument('--offline', action='store_true', help="Force offline mode by clearing GEMINI_API_KEY")

    def handle(self, *args, **options):
        dataset_name = options['dataset']
        limit = options['limit']
        if options['offline']:
            os.environ['GEMINI_API_KEY'] = ""

        # Get benchmark path
        data_dir = os.path.join(settings.BASE_DIR, 'data')
        benchmark_path = os.path.join(data_dir, dataset_name)

        if not os.path.exists(benchmark_path):
            self.stdout.write(self.style.ERROR(
                f"Clinical validation dataset not found at {benchmark_path}.\n"
                "Please run 'python data/generate_benchmarks.py' first to create the benchmark files."
            ))
            return

        with open(benchmark_path, 'r', encoding='utf-8') as f:
            cases = json.load(f)

        if limit > 0:
            cases = cases[:limit]

        self.stdout.write(f"Loaded {len(cases)} clinical benchmark profiles. Starting evaluation...")

        # Output folder for reports
        reports_dir = os.path.join(settings.BASE_DIR, 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        y_true = []
        y_pred = []
        y_scores = []  # To store scores for ROC-AUC
        response_times = []
        audit_log = []

        # Connect RiskEngine
        risk_engine = RiskEngine()

        for idx, case in enumerate(cases):
            patient_id = case["patient_id"]
            self.stdout.write(f" [{idx+1}/{len(cases)}] Evaluating profile {patient_id}...")

            expected_risk = normalize_risk(case["expected_risk"])
            
            # Setup database transaction to prevent DB pollution
            start_time = time.perf_counter()
            with transaction.atomic():
                try:
                    # Create temporary patient profile
                    username = f"eval_temp_{patient_id}_{idx}"
                    user = User.objects.create_user(username=username, password="password123")
                    
                    from decimal import Decimal
                    egfr_val = case.get("lab_values", {}).get("eGFR")
                    if egfr_val is not None:
                        egfr_val = Decimal(str(egfr_val))
                    creatinine_val = case.get("lab_values", {}).get("Creatinine")
                    if creatinine_val is not None:
                        creatinine_val = Decimal(str(creatinine_val))

                    profile = PatientProfile.objects.create(
                        user=user,
                        age=case.get("age", 30),
                        gender='M' if case.get("gender", "").lower() == 'male' else 'F' if case.get("gender", "").lower() == 'female' else 'O',
                        pregnancy_status=case.get("pregnant", False),
                        allergies=case.get("allergies", []),
                        chronic_diseases=case.get("medical_conditions", []),
                        egfr=egfr_val,
                        creatinine=creatinine_val
                    )

                    # Add active cabinet medications
                    for med_name in case.get("current_medications", []) + case.get("new_medications", []):
                        MedicationCabinet.objects.create(
                            patient=profile,
                            name=med_name,
                            dosage="default",
                            frequency="default",
                            start_date=datetime.now().date(),
                            is_active=True
                        )

                    # Execute safety evaluation
                    eval_start = time.perf_counter()
                    result = risk_engine.evaluate_patient_safety(profile)
                    eval_time_ms = (time.perf_counter() - eval_start) * 1000.0
                    response_times.append(eval_time_ms)

                    predicted_risk = normalize_risk(result.get("overall_risk_score", "Safe"))

                    # Record ground truth and prediction
                    y_true.append(expected_risk)
                    y_pred.append(predicted_risk)

                    # Build probability vector for ROC-AUC calculation
                    # Since it is a rule-based/schema output, we assign a 1.0 probability to predicted class, 0.0 to others
                    score_vector = [1.0 if l == predicted_risk else 0.0 for l in RISK_LABELS]
                    y_scores.append(score_vector)

                    # Check matched rules / alerts
                    triggered = [i["description"] for i in result.get("interactions", [])]
                    notes = result.get("clinician_notes", "")
                    refs = result.get("evidence_references", [])

                    passed = (predicted_risk == expected_risk)

                    audit_log.append({
                        "patient_id": patient_id,
                        "age": case.get("age"),
                        "gender": case.get("gender"),
                        "expected_risk": expected_risk,
                        "predicted_risk": predicted_risk,
                        "passed": passed,
                        "latency_ms": eval_time_ms,
                        "triggered_alerts": "; ".join(triggered),
                        "references": "; ".join(refs),
                        "notes": notes
                    })

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error evaluating patient {patient_id}: {e}"))
                finally:
                    # Rollback transaction to keep the DB pristine
                    transaction.set_rollback(True)

        # 1. Compute Metrics using sklearn
        y_true_normalized = [RISK_LABELS.index(y) for y in y_true]
        y_pred_normalized = [RISK_LABELS.index(y) for y in y_pred]

        # Overall Accuracy
        overall_acc = accuracy_score(y_true, y_pred) * 100.0

        # Precision, Recall, F1
        precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='macro', zero_division=0)
        precision_pct = precision * 100.0
        recall_pct = recall * 100.0
        f1_pct = f1 * 100.0

        # Specificity calculation per class (One-vs-All)
        cm = confusion_matrix(y_true, y_pred, labels=RISK_LABELS)
        specificities = []
        sensitivities = []
        for i in range(len(RISK_LABELS)):
            tp = cm[i, i]
            fn = sum(cm[i, :]) - tp
            fp = sum(cm[:, i]) - tp
            tn = sum(sum(cm)) - tp - fp - fn
            spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            specificities.append(spec)
            sensitivities.append(sens)
        
        avg_specificity = np.mean(specificities) * 100.0
        avg_sensitivity = np.mean(sensitivities) * 100.0
        balanced_acc = (avg_sensitivity + avg_specificity) / 2.0

        # Calculate ROC-AUC Score
        try:
            # Binarize labels
            y_true_bin = label_binarize(y_true, classes=RISK_LABELS)
            y_scores_arr = np.array(y_scores)
            roc_auc = roc_auc_score(y_true_bin, y_scores_arr, average='macro', multi_class='ovr')
        except Exception:
            roc_auc = 0.0

        avg_latency = sum(response_times) / len(response_times)

        # Print Console Dashboard
        self.stdout.write("\n" + "=" * 54)
        self.stdout.write("      MedGuardian AI Clinical Evaluation Dashboard")
        self.stdout.write("=" * 54)
        self.stdout.write(f"Patients Tested        : {len(cases)}")
        self.stdout.write(f"Correct Predictions    : {sum(1 for a in audit_log if a['passed'])}")
        self.stdout.write(f"Incorrect Predictions  : {sum(1 for a in audit_log if not a['passed'])}")
        self.stdout.write(f"Accuracy               : {overall_acc:.2f}%")
        self.stdout.write(f"Precision (Macro)      : {precision_pct:.2f}%")
        self.stdout.write(f"Recall (Sensitivity)   : {recall_pct:.2f}%")
        self.stdout.write(f"F1 Score               : {f1_pct:.2f}%")
        self.stdout.write(f"Specificity (Average)  : {avg_specificity:.2f}%")
        self.stdout.write(f"Balanced Accuracy      : {balanced_acc:.2f}%")
        self.stdout.write(f"Average Response Time  : {avg_latency:.2f} ms")
        self.stdout.write("=" * 54 + "\n")

        # 2. Save CSV and JSON logs
        df_results = pd.DataFrame(audit_log)
        df_results.to_csv(os.path.join(reports_dir, "results.csv"), index=False)
        
        # Save simple audit log CSV
        audit_csv_path = os.path.join(reports_dir, "audit_log.csv")
        with open(audit_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=audit_log[0].keys())
            writer.writeheader()
            writer.writerows(audit_log)

        # Save metrics JSON
        metrics_json_path = os.path.join(reports_dir, "metrics.json")
        metrics_out = {
            "evaluation_date": datetime.now().isoformat(),
            "total_cases": len(cases),
            "accuracy": overall_acc,
            "precision_macro": precision_pct,
            "recall_macro": recall_pct,
            "f1_score_macro": f1_pct,
            "specificity_average": avg_specificity,
            "balanced_accuracy": balanced_acc,
            "roc_auc": roc_auc,
            "average_latency_ms": avg_latency
        }
        with open(metrics_json_path, 'w', encoding='utf-8') as f:
            json.dump(metrics_out, f, indent=2)

        # Save classification report TXT
        report_txt_path = os.path.join(reports_dir, "classification_report.txt")
        report_text = classification_report(y_true, y_pred, labels=RISK_LABELS, zero_division=0)
        with open(report_txt_path, 'w', encoding='utf-8') as f:
            f.write(report_text)

        # 3. Plot Confusion Matrix
        self.plot_confusion_matrix(cm, RISK_LABELS, os.path.join(reports_dir, "confusion_matrix.png"))

        # 4. Plot ROC Curve
        self.plot_roc_curve(y_true, y_scores, RISK_LABELS, os.path.join(reports_dir, "roc_curve.png"))

        # 5. Generate PDF Report
        pdf_path = os.path.join(reports_dir, "accuracy_report.pdf")
        self.generate_pdf_report(pdf_path, metrics_out, audit_log, reports_dir)

        self.stdout.write(self.style.SUCCESS(f"Saved evaluation reports to backend/reports/ folder:"))
        self.stdout.write(self.style.SUCCESS(f" - CSV Results          : backend/reports/results.csv"))
        self.stdout.write(self.style.SUCCESS(f" - Audit Log            : backend/reports/audit_log.csv"))
        self.stdout.write(self.style.SUCCESS(f" - Metrics JSON         : backend/reports/metrics.json"))
        self.stdout.write(self.style.SUCCESS(f" - Classification Report: backend/reports/classification_report.txt"))
        self.stdout.write(self.style.SUCCESS(f" - Confusion Matrix PNG : backend/reports/confusion_matrix.png"))
        self.stdout.write(self.style.SUCCESS(f" - ROC Curve PNG        : backend/reports/roc_curve.png"))
        self.stdout.write(self.style.SUCCESS(f" - PDF Accuracy Report  : backend/reports/accuracy_report.pdf"))

    def plot_confusion_matrix(self, cm, labels, save_path):
        plt.figure(figsize=(6, 5))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title('Clinical Risk Classification Confusion Matrix')
        plt.colorbar()
        tick_marks = np.arange(len(labels))
        plt.xticks(tick_marks, labels, rotation=45)
        plt.yticks(tick_marks, labels)

        # Add text labels inside matrix
        thresh = cm.max() / 2.
        for i, j in np.ndindex(cm.shape):
            plt.text(j, i, format(cm[i, j], 'd'),
                     horizontalalignment="center",
                     color="white" if cm[i, j] > thresh else "black")

        plt.tight_layout()
        plt.ylabel('Ground Truth Clinical Label')
        plt.xlabel('MedGuardian Predicted Label')
        plt.savefig(save_path, dpi=300)
        plt.close()

    def plot_roc_curve(self, y_true, y_scores, labels, save_path):
        plt.figure(figsize=(6, 5))
        try:
            # Binarize labels
            y_true_bin = label_binarize(y_true, classes=labels)
            y_scores_arr = np.array(y_scores)
            
            for i in range(len(labels)):
                fpr, tpr, _ = roc_curve(y_true_bin[:, i], y_scores_arr[:, i])
                plt.plot(fpr, tpr, label=f'{labels[i]} (AUC = {roc_auc_score(y_true_bin[:, i], y_scores_arr[:, i]):.2f})')
            
            plt.plot([0, 1], [0, 1], 'k--', label='Random Guessing')
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('False Positive Rate (1 - Specificity)')
            plt.ylabel('True Positive Rate (Sensitivity)')
            plt.title('Receiver Operating Characteristic (ROC) Curve')
            plt.legend(loc="lower right")
        except Exception as e:
            plt.text(0.5, 0.5, f"ROC Plot Unavailable:\n{e}", ha='center', va='center')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close()

    def generate_pdf_report(self, pdf_path, metrics, audit_log, reports_dir):
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
            fontSize=8,
            leading=10
        )

        story = []

        # Header
        story.append(Paragraph("MedGuardian AI — Clinical Validation Report", title_style))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Patients Tested: {metrics['total_cases']}", subtitle_style))
        story.append(Spacer(1, 10))

        # Metrics Card Table
        summary_data = [
            [
                Paragraph("<b>Accuracy</b>", cell_text), 
                Paragraph("<b>Precision</b>", cell_text), 
                Paragraph("<b>Sensitivity</b>", cell_text),
                Paragraph("<b>F1 Score</b>", cell_text)
            ],
            [
                f"{metrics['accuracy']:.2f}%", 
                f"{metrics['precision_macro']:.2f}%", 
                f"{metrics['recall_macro']:.2f}%", 
                f"{metrics['f1_score_macro']:.2f}%"
            ],
            [
                Paragraph("<b>Specificity</b>", cell_text), 
                Paragraph("<b>Balanced Acc</b>", cell_text), 
                Paragraph("<b>ROC-AUC</b>", cell_text), 
                Paragraph("<b>Avg Latency</b>", cell_text)
            ],
            [
                f"{metrics['specificity_average']:.2f}%", 
                f"{metrics['balanced_accuracy']:.2f}%", 
                f"{metrics['roc_auc']:.2f}", 
                f"{metrics['average_latency_ms']:.2f} ms"
            ]
        ]
        
        summary_table = Table(summary_data, colWidths=[130]*4)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EDF2F7')),
            ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#EDF2F7')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
            ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
        ]))
        
        story.append(Paragraph("1. Performance Metrics Summary", section_heading))
        story.append(summary_table)
        story.append(Spacer(1, 15))

        # Add Figures
        cm_img_path = os.path.join(reports_dir, "confusion_matrix.png")
        roc_img_path = os.path.join(reports_dir, "roc_curve.png")
        
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
        story.append(Paragraph("2. Diagnostic Plots", section_heading))
        story.append(img_table)
        story.append(Spacer(1, 15))

        # Audit Table (Summary of Cases)
        story.append(Paragraph("3. Patient Audit Log", section_heading))
        audit_headers = [
            Paragraph("<b>Patient ID</b>", cell_text),
            Paragraph("<b>Age</b>", cell_text),
            Paragraph("<b>Expected Risk</b>", cell_text),
            Paragraph("<b>Predicted Risk</b>", cell_text),
            Paragraph("<b>Result</b>", cell_text),
            Paragraph("<b>Matched Alerts</b>", cell_text)
        ]
        
        audit_rows = [audit_headers]
        for log in audit_log[:15]: # Show first 15 in the PDF table for page-budget constraints
            passed_text = "<font color='green'><b>PASS</b></font>" if log["passed"] else "<font color='red'><b>FAIL</b></font>"
            audit_rows.append([
                Paragraph(log["patient_id"], cell_text),
                Paragraph(str(log["age"]), cell_text),
                Paragraph(log["expected_risk"], cell_text),
                Paragraph(log["predicted_risk"], cell_text),
                Paragraph(passed_text, cell_text),
                Paragraph(log["triggered_alerts"][:90] + "..." if len(log["triggered_alerts"]) > 90 else log["triggered_alerts"], cell_text)
            ])

        audit_table = Table(audit_rows, colWidths=[60, 40, 80, 80, 50, 230])
        audit_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EDF2F7')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(audit_table)
        
        if len(audit_log) > 15:
            story.append(Spacer(1, 5))
            story.append(Paragraph(f"<i>* Showing first 15 of {len(audit_log)} total patient case records. See backend/reports/results.csv for full log.</i>", cell_text))

        # Build document
        doc.build(story)
