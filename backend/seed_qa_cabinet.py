import os
import sys
import datetime
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medguardian.settings')

import django
django.setup()

from django.contrib.auth.models import User
from patients.models import PatientProfile, MedicationCabinet, SafetyAssessmentHistory
from services.risk_engine import RiskEngine

def seed_cabinet():
    user = User.objects.get(username='testuser_qa')
    profile = user.profile
    
    # Ensure profile has eGFR and Creatinine populated for realistic synthetic profile
    profile.creatinine = 0.95
    profile.egfr = 85.00
    profile.save()

    print(f"Profile updated: eGFR={profile.egfr}, Creatinine={profile.creatinine}")

    # Check existing medications
    existing_names = set(profile.medications.values_list('name', flat=True))
    print(f"Initial active medications ({len(existing_names)}): {list(existing_names)}")

    additional_meds = [
        {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily", "start_date": datetime.date(2025, 2, 1)},
        {"name": "Levothyroxine", "dosage": "50mcg", "frequency": "Once daily morning", "start_date": datetime.date(2025, 2, 20)},
        {"name": "Omeprazole", "dosage": "20mg", "frequency": "Once daily before breakfast", "start_date": datetime.date(2025, 3, 15)},
        {"name": "Amlodipine", "dosage": "5mg", "frequency": "Once daily", "start_date": datetime.date(2025, 4, 1)},
        {"name": "Cetirizine", "dosage": "10mg", "frequency": "Once daily as needed", "start_date": datetime.date(2025, 5, 10)},
        {"name": "Vitamin D3", "dosage": "1000IU", "frequency": "Once daily", "start_date": datetime.date(2025, 6, 1)},
        {"name": "Acetaminophen", "dosage": "500mg", "frequency": "Every 6 hours PRN", "start_date": datetime.date(2025, 7, 1)},
        {"name": "Calcium Carbonate", "dosage": "500mg", "frequency": "Once daily with food", "start_date": datetime.date(2025, 8, 1)},
    ]

    for m in additional_meds:
        if m["name"] not in existing_names:
            MedicationCabinet.objects.create(
                patient=profile,
                name=m["name"],
                dosage=m["dosage"],
                frequency=m["frequency"],
                start_date=m["start_date"],
                is_active=True
            )
            print(f"Added {m['name']} ({m['dosage']}) - start date: {m['start_date']}")

    med_count = profile.medications.filter(is_active=True).count()
    print(f"Total cabinet medications now: {med_count}")

    # Seed historical safety assessments across past dates so history timeline is populated with distinct dates
    historical_dates = [
        (datetime.datetime(2025, 1, 5, 10, 0, tzinfo=timezone.utc), "Safe", "lab_update", "Baseline Clinical Intake"),
        (datetime.datetime(2025, 2, 2, 14, 30, tzinfo=timezone.utc), "Moderate", "medication_change", "Metformin Added"),
        (datetime.datetime(2025, 3, 16, 9, 15, tzinfo=timezone.utc), "Moderate", "medication_change", "Omeprazole Regimen Initiated"),
        (datetime.datetime(2025, 5, 12, 11, 0, tzinfo=timezone.utc), "Low", "lab_update", "Quarterly Renal Panel"),
        (datetime.datetime(2025, 8, 2, 16, 45, tzinfo=timezone.utc), "Moderate", "medication_change", "Calcium Supplementation Started"),
    ]

    for dt, risk, trigger, note in historical_dates:
        h, created = SafetyAssessmentHistory.objects.get_or_create(
            patient=profile,
            triggered_by=trigger,
            risk_score=risk,
            defaults={
                'details': {
                    'overall_risk_score': risk,
                    'clinician_notes': note,
                    'evidence_references': ['who_guidelines.txt', 'clinical_benchmark.json'],
                    'interactions': []
                }
            }
        )
        # Update created_at directly
        SafetyAssessmentHistory.objects.filter(pk=h.pk).update(created_at=dt)

    hist_count = profile.safety_history.count()
    print(f"Total safety history records: {hist_count}")

if __name__ == '__main__':
    seed_cabinet()
