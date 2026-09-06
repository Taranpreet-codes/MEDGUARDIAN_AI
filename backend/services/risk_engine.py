"""
services/risk_engine.py — Clinical Risk Engine Adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Maintains backwards-compatible interface for PatientProfileViewSet,
Celery background tasks, and Stage 1 / Stage 2 test suites while
delegating core logic to the provider-based ClinicalDataService.

NOTE: RxNav's Drug-Drug Interaction API was discontinued on Jan 2, 2024.
Interaction checking is now routed through the CompositeInteractionProvider
(Curated Clinical DDI DB + openFDA SPL) rather than the discontinued endpoint.
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field
from patients.models import PatientProfile, InteractionLog
from .clinical_service import ClinicalDataService
from .rag import RAGEngine

logger = logging.getLogger(__name__)


# Pydantic schemas for Gemini Risk Evaluator (preserved for backwards compatibility)
class WarningDetail(BaseModel):
    severity: str = Field(description="Warning severity: Severe, Moderate, or Low")
    description: str = Field(description="Explanation of the safety warning, interaction, or dosage conflict")
    drug_involved: str = Field(description="Specific drug(s) causing the alert")


class SafetyEvaluation(BaseModel):
    overall_risk_score: str = Field(description="Highest risk tier detected: Severe, Moderate, Low, or Safe")
    interactions: list[WarningDetail] = Field(description="Detailed clinical warnings generated")
    evidence_references: list[str] = Field(description="Clinical document names or guidelines referenced from the context")
    clinician_notes: str = Field(description="Professional summary of considerations for the treating physician")


class RiskEngine:
    """
    Adapter class wrapping ClinicalDataService with backwards-compatible methods.
    """

    def __init__(self):
        self.clinical_service = ClinicalDataService()
        self.rag_engine = RAGEngine()
        self.api_key = os.environ.get("GEMINI_API_KEY", "")

    def resolve_rxcui(self, drug_name: str) -> Optional[str]:
        """Resolves generic drug name to RxNorm RxCUI using RxNavNormalizerProvider."""
        normalized = self.clinical_service.normalizer.normalize(drug_name)
        return normalized.rxcui

    def check_rxnav_interactions(self, meds: List[str]) -> List[Dict[str, Any]]:
        """
        Evaluates drug-drug interactions among medication names.
        Routes through the CompositeInteractionProvider (Curated DDI + openFDA)
        since RxNav discontinued its DDI API on Jan 2, 2024.
        """
        normalized_meds = self.clinical_service.normalize_medications(meds)
        alerts = self.clinical_service.evaluate_interactions(normalized_meds)
        return [
            {
                "severity": a.severity if a.severity != "Contraindicated" else "Severe",
                "description": a.description,
                "drug_involved": a.drug_involved
            }
            for a in alerts
        ]

    def evaluate_patient_safety(self, profile: PatientProfile) -> Dict[str, Any]:
        """
        Gathers profile, active medications, evaluates interactions via providers,
        queries clinical guidelines, and returns structured safety evaluation.
        """
        return self.clinical_service.evaluate_patient_safety(profile)
