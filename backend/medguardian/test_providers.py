"""
medguardian/test_providers.py — Unit Tests for Provider-Based Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validates:
1. RxNav Normalization (brand to generic, RxCUI resolution, no interaction API).
2. Curated DDI Provider (standardized severity, mechanism, clinical actions).
3. openFDA Label Provider (label warnings, rate-limit tolerance).
4. Composite Interaction Provider (tiered structured + label excerpt).
5. ClinicalDataService End-to-End with both known and previously unseen queries.
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from unittest.mock import patch, MagicMock
from services.providers import (
    RxNavNormalizerProvider,
    CuratedDDIProvider,
    OpenFDALabelProvider,
    CompositeInteractionProvider,
    ChromaGuidelineProvider,
    FallbackClinicalProvider,
    NormalizedDrug,
    InteractionAlert,
    DrugLabelInfo,
)
from services.clinical_service import ClinicalDataService
from patients.models import PatientProfile, MedicationCabinet
from django.contrib.auth.models import User


class ProviderArchitectureTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testdr", password="password123")
        self.profile = PatientProfile.objects.create(
            user=self.user,
            age=62,
            gender="M",
            pregnancy_status=False,
            egfr=Decimal("28.00"),  # Severe renal impairment
            creatinine=Decimal("2.80"),
            allergies=["Penicillin"]
        )

    def test_01_rxnav_normalization(self):
        """Validates drug normalization: resolves brands to generics and RxCUIs without calling discontinued DDI API."""
        normalizer = RxNavNormalizerProvider()

        # Test brand-to-generic canonical resolution
        drug_glucophage = normalizer.normalize("Glucophage")
        self.assertEqual(drug_glucophage.generic_name, "metformin")
        self.assertEqual(drug_glucophage.rxcui, "6809")

        drug_prinivil = normalizer.normalize("Prinivil")
        self.assertEqual(drug_prinivil.generic_name, "lisinopril")
        self.assertEqual(drug_prinivil.rxcui, "29046")

        drug_lipitor = normalizer.normalize("Lipitor")
        self.assertEqual(drug_lipitor.generic_name, "atorvastatin")
        self.assertEqual(drug_lipitor.rxcui, "83367")

        # Test caching
        cached_result = normalizer.normalize("Glucophage")
        self.assertIs(cached_result, drug_glucophage)

    def test_02_curated_ddi_provider(self):
        """Validates CuratedDDIProvider pair lookups, commutative keys, and standardized severity."""
        provider = CuratedDDIProvider()

        # Lisinopril + Spironolactone -> Severe (Hyperkalemia)
        alert = provider.check_pair("lisinopril", "spironolactone")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "Severe")
        self.assertIn("potassium", alert.mechanism.lower())
        self.assertIn("hyperkalemia", alert.clinical_management.lower())

        # Commutative lookup (B + A)
        alert_reverse = provider.check_pair("spironolactone", "lisinopril")
        self.assertIsNotNone(alert_reverse)
        self.assertEqual(alert_reverse.severity, "Severe")

        # Warfarin + Aspirin -> Severe (Bleeding)
        alert_bleeding = provider.check_pair("warfarin", "aspirin")
        self.assertIsNotNone(alert_bleeding)
        self.assertEqual(alert_bleeding.severity, "Severe")
        self.assertIn("hemorrhage", alert_bleeding.clinical_management.lower())

        # Simvastatin + Amiodarone -> Severe (Rhabdomyolysis)
        alert_statin = provider.check_pair("simvastatin", "amiodarone")
        self.assertIsNotNone(alert_statin)
        self.assertEqual(alert_statin.severity, "Severe")

    def test_03_openfda_label_provider(self):
        """Validates OpenFDALabelProvider parsing and mock resilience."""
        provider = OpenFDALabelProvider()

        # Test with mocked openFDA response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{
                "boxed_warning": ["WARNING: FETAL TOXICITY - When pregnancy is detected, discontinue Lisinopril as soon as possible."],
                "contraindications": ["Lisinopril is contraindicated in patients with a history of angioedema."],
                "drug_interactions": ["Concomitant use of Lisinopril with potassium supplements may lead to increases of serum potassium."],
                "dosage_and_administration": ["Initial adult dose is 10 mg once daily."]
            }]
        }

        with patch('requests.get', return_value=mock_response):
            label = provider.get_label_info("lisinopril")
            self.assertIsNotNone(label)
            self.assertIn("FETAL TOXICITY", label.boxed_warning)
            self.assertIn("angioedema", label.contraindications)
            self.assertIn("potassium", label.drug_interactions)

            # Test label interaction search
            excerpt = provider.search_label_interaction("lisinopril", "potassium")
            self.assertIsNotNone(excerpt)
            self.assertIn("potassium", excerpt.lower())

    def test_04_composite_interaction_provider(self):
        """Validates Tiered Composite Provider merging structured DDI with FDA label excerpts."""
        curated = CuratedDDIProvider()
        mock_openfda = MagicMock(spec=OpenFDALabelProvider)
        mock_openfda.search_label_interaction.return_value = "Official FDA Label: Monitor serum potassium closely when combined with ACE inhibitors."

        composite = CompositeInteractionProvider(curated_provider=curated, openfda_provider=mock_openfda)

        meds = [
            NormalizedDrug(input_name="Lisinopril", generic_name="lisinopril"),
            NormalizedDrug(input_name="Aldactone", generic_name="spironolactone")
        ]

        alerts = composite.check_interactions(meds)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "Severe")
        self.assertIn("openFDA SPL", alerts[0].source)
        self.assertIsNotNone(alerts[0].fda_label_excerpt)

    def test_05_clinical_data_service_end_to_end_renal_and_unseen_queries(self):
        """
        Validates ClinicalDataService generic evaluation:
        - Evaluates patient with eGFR 28 (Severe CKD) on Metformin -> triggers contraindication.
        - Evaluates Penicillin allergy against Amoxicillin -> triggers allergy warning.
        - Evaluates unseen drug pair (Atorvastatin + Clarithromycin).
        """
        service = ClinicalDataService()

        # Add active medications to profile
        MedicationCabinet.objects.create(
            patient=self.profile,
            name="Glucophage",  # Brand for Metformin
            dosage="500mg",
            frequency="twice daily",
            start_date=datetime.date.today(),
            is_active=True
        )
        MedicationCabinet.objects.create(
            patient=self.profile,
            name="Amoxicillin",  # Penicillin class
            dosage="500mg",
            frequency="three times daily",
            start_date=datetime.date.today(),
            is_active=True
        )

        # Evaluate safety with new unseen drug pair (Atorvastatin + Clarithromycin)
        evaluation = service.evaluate_patient_safety(
            self.profile,
            new_meds=["Atorvastatin", "Clarithromycin"]
        )

        self.assertEqual(evaluation["overall_risk_score"], "Severe")
        descriptions = [w["description"].lower() for w in evaluation["interactions"]]

        # 1. Check renal contraindication for Metformin at eGFR 28 (< 30)
        self.assertTrue(any("metformin is contraindicated in severe renal impairment" in d or "lactic acidosis" in d for d in descriptions))

        # 2. Check allergy alert for Penicillin allergy with Amoxicillin
        self.assertTrue(any("allergic" in d and "amoxicillin" in d for d in descriptions))

        # 3. Check previously unseen DDI (Atorvastatin + Clarithromycin)
        self.assertTrue(any("clarithromycin" in d or "rhabdomyolysis" in d for d in descriptions))

        # 4. Verify clinician notes and evidence references
        self.assertTrue(len(evaluation["evidence_references"]) > 0)
        self.assertIn("Provider-based clinical evaluation completed", evaluation["clinician_notes"])
