"""
services/clinical_service.py — Unified Provider-Based Clinical Data Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Coordinates:
- Drug Normalization (RxNav Active APIs)
- Drug-Drug Interaction Evaluation (Curated Clinical DB + openFDA SPL)
- Clinical Label Warnings & Contraindications (openFDA)
- Guideline Evidence & Relevance Scores (ChromaDB)
- Resilient Offline Circuit Breaker
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional

from .providers import (
    NormalizedDrug,
    DrugLabelInfo,
    InteractionAlert,
    EvidenceCitation,
    RxNavNormalizerProvider,
    OpenFDALabelProvider,
    CuratedDDIProvider,
    CompositeInteractionProvider,
    ChromaGuidelineProvider,
    FallbackClinicalProvider,
)

logger = logging.getLogger(__name__)


class ClinicalDataService:
    """
    Central orchestration service for clinical evaluations using provider abstractions.
    """

    def __init__(
        self,
        normalizer: Optional[RxNavNormalizerProvider] = None,
        interaction_provider: Optional[CompositeInteractionProvider] = None,
        label_provider: Optional[OpenFDALabelProvider] = None,
        evidence_provider: Optional[ChromaGuidelineProvider] = None,
        fallback_provider: Optional[FallbackClinicalProvider] = None,
    ):
        self.normalizer = normalizer or RxNavNormalizerProvider()
        self.label_provider = label_provider or OpenFDALabelProvider()
        self.curated_ddi = CuratedDDIProvider()
        self.interaction_provider = interaction_provider or CompositeInteractionProvider(
            curated_provider=self.curated_ddi,
            openfda_provider=self.label_provider
        )
        self.evidence_provider = evidence_provider or ChromaGuidelineProvider()
        self.fallback_provider = fallback_provider or FallbackClinicalProvider()

    def normalize_medications(self, med_names: List[str]) -> List[NormalizedDrug]:
        """Normalizes a list of medication names to canonical generic entities."""
        return [self.normalizer.normalize(name) for name in med_names if name.strip()]

    def evaluate_interactions(self, meds: List[NormalizedDrug]) -> List[InteractionAlert]:
        """Evaluates drug-drug interactions using composite provider with fallback."""
        try:
            alerts = self.interaction_provider.check_interactions(meds)
            if not alerts and len(meds) >= 2:
                # Check fallback provider as circuit breaker
                alerts = self.fallback_provider.check_interactions(meds)
            return alerts
        except Exception as e:
            logger.warning(f"Primary interaction provider failed ({e}). Using circuit breaker fallback.")
            return self.fallback_provider.check_interactions(meds)

    def evaluate_patient_safety(self, profile, new_meds: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Comprehensive clinical safety evaluation for a patient profile.
        Checks:
        1. Drug-Drug Interactions
        2. Pregnancy contraindications
        3. Renal function & lab-based precautions
        4. Patient allergy matching
        5. Verified clinical guideline citations
        """
        # 1. Gather active medications
        from patients.models import MedicationCabinet, InteractionLog

        cabinet_meds = list(MedicationCabinet.objects.filter(patient=profile, is_active=True).values_list('name', flat=True))
        all_med_names = list(cabinet_meds)
        if new_meds:
            all_med_names.extend(new_meds)

        if not all_med_names:
            return {
                "overall_risk_score": "Safe",
                "interactions": [],
                "evidence_references": ["Patient profile contains 0 active medications."],
                "clinician_notes": "No medications currently active. Maintain healthy lifestyle."
            }

        # 2. Normalize medications
        normalized_meds = self.normalize_medications(all_med_names)
        generic_names = {m.generic_name.lower().strip() for m in normalized_meds if m.generic_name}

        warnings: List[Dict[str, Any]] = []
        highest_severity = "Safe"

        def escalate_risk(sev: str):
            nonlocal highest_severity
            order = {"Safe": 0, "Low": 1, "Moderate": 2, "Severe": 3, "Contraindicated": 4}
            # Map Contraindicated to Severe for high-level scoring
            canonical_sev = "Severe" if sev in ("Severe", "Contraindicated") else sev
            if order.get(canonical_sev, 0) > order.get(highest_severity, 0):
                highest_severity = canonical_sev

        # 3. Drug-Drug Interactions
        interaction_alerts = self.evaluate_interactions(normalized_meds)
        for alert in interaction_alerts:
            warnings.append({
                "severity": alert.severity if alert.severity != "Contraindicated" else "Severe",
                "category": "drug_interaction",
                "description": alert.description,
                "drug_involved": alert.drug_involved,
                "mechanism": alert.mechanism,
                "clinical_management": alert.clinical_management,
                "source": alert.source,
                "fda_label_excerpt": alert.fda_label_excerpt
            })
            escalate_risk(alert.severity)

        # 4. Patient Pregnancy Contraindications
        if profile.pregnancy_status:
            # Known severe teratogens
            pregnancy_contraindications = {
                "lisinopril": "Lisinopril is contraindicated in pregnancy due to risks of fetal toxicity and birth defects.",
                "losartan": "Losartan is contraindicated in pregnancy due to risks of oligohydramnios and fetal harm.",
                "enalapril": "Enalapril is contraindicated in pregnancy; RAAS inhibitors cause major fetal anomalies.",
                "methotrexate": "Methotrexate is strictly contraindicated in pregnancy due to embryotoxicity and congenital malformations.",
                "warfarin": "Warfarin crosses the placenta causing fetal warfarin syndrome and embryopathy.",
                "simvastatin": "Statins are contraindicated during pregnancy due to disruption of fetal cholesterol synthesis.",
                "atorvastatin": "Atorvastatin is contraindicated in pregnant patients due to potential fetal toxicity."
            }
            for gen in generic_names:
                for contra_drug, msg in pregnancy_contraindications.items():
                    if contra_drug in gen:
                        warnings.append({
                            "severity": "Severe",
                            "category": "pregnancy_contraindication",
                            "description": msg,
                            "drug_involved": gen.capitalize(),
                            "source": "FDA Boxed Warning / WHO Guidelines"
                        })
                        escalate_risk("Severe")

        # 5. Renal Function & Lab Precautions (eGFR and Creatinine)
        if profile.egfr:
            try:
                egfr_val = float(profile.egfr)
                if egfr_val < 30:
                    # Severe CKD (Stage 4-5)
                    if "metformin" in generic_names:
                        warnings.append({
                            "severity": "Severe",
                            "category": "renal_precaution",
                            "description": f"Metformin is contraindicated in severe renal impairment (eGFR {egfr_val} < 30 mL/min/1.73m²) due to high risk of fatal lactic acidosis.",
                            "drug_involved": "Metformin",
                            "source": "FDA Drug Label / KDIGO 2023"
                        })
                        escalate_risk("Severe")
                    if "spironolactone" in generic_names:
                        warnings.append({
                            "severity": "Severe",
                            "category": "renal_precaution",
                            "description": f"Spironolactone is contraindicated in advanced kidney disease (eGFR {egfr_val} < 30) due to severe hyperkalemia risk.",
                            "drug_involved": "Spironolactone",
                            "source": "FDA Drug Label"
                        })
                        escalate_risk("Severe")
                elif egfr_val < 45:
                    # Moderate-Severe CKD
                    if "metformin" in generic_names:
                        warnings.append({
                            "severity": "Moderate",
                            "category": "renal_precaution",
                            "description": f"Renal dosage adjustment required: eGFR {egfr_val} mL/min. Maximum recommended Metformin dose is 1000 mg/day.",
                            "drug_involved": "Metformin",
                            "source": "FDA Drug Label / ADA Guidelines"
                        })
                        escalate_risk("Moderate")

                if egfr_val < 45:
                    if "ibuprofen" in generic_names:
                        warnings.append({
                            "severity": "Moderate",
                            "category": "renal_precaution",
                            "description": f"Patient has renal impairment (eGFR {egfr_val}). NSAIDs like Ibuprofen should be avoided or minimized.",
                            "drug_involved": "Ibuprofen",
                            "source": "KDIGO Guidelines"
                        })
                        escalate_risk("Moderate")
            except (ValueError, TypeError):
                pass

        # 6. Patient Allergy Matching
        patient_allergies = [a.lower().strip() for a in (profile.allergies or []) if a.strip()]
        for allergy in patient_allergies:
            for gen in generic_names:
                is_allergic = False
                if allergy in gen:
                    is_allergic = True
                elif allergy == "penicillin" and any(b in gen for b in ["amox", "ampicil", "penicil"]):
                    is_allergic = True
                elif allergy == "sulfa" and any(s in gen for s in ["sulfameth", "bactrim", "sulfadiazine"]):
                    is_allergic = True

                if is_allergic:
                    warnings.append({
                        "severity": "Severe",
                        "category": "allergy_conflict",
                        "description": f"Potential allergic reaction: Patient is allergic to {allergy.capitalize()} and active medication regimen contains {gen.capitalize()}.",
                        "drug_involved": gen.capitalize(),
                        "source": "Patient Allergy Record / Clinical Safety Rules"
                    })
                    escalate_risk("Severe")

        # 7. Guideline Evidence Citations
        citations: List[EvidenceCitation] = []
        for gen in list(generic_names)[:4]:
            query = f"{gen} clinical guideline warnings"
            cits = self.evidence_provider.retrieve_evidence(query, limit=2)
            citations.extend(cits)

        evidence_references = [c.source for c in citations] if citations else ["openFDA Drug Label Database", "Curated Clinical DDI Database"]
        # Deduplicate evidence references
        evidence_references = list(dict.fromkeys(evidence_references))

        # 8. Scope & Clinical Disclaimer
        clinician_notes = (
            "Provider-based clinical evaluation completed. "
            f"{len(warnings)} clinical alert(s) identified. "
            "Evaluated against RxNav normalization, openFDA drug labels, and Curated Clinical DDI dataset. "
            "Always corroborate with treating clinician judgment."
        )

        details = {
            "overall_risk_score": highest_severity,
            "interactions": warnings,
            "evidence_references": evidence_references,
            "clinician_notes": clinician_notes
        }

        # Cache log
        try:
            InteractionLog.objects.create(
                patient=profile,
                risk_score=highest_severity,
                details=details
            )
        except Exception as e:
            logger.debug(f"Could not write InteractionLog: {e}")

        return details
