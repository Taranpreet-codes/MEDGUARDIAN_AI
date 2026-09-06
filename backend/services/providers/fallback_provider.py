"""
services/providers/fallback_provider.py — Offline Circuit Breaker Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides offline, deterministic fallback for clinical safety evaluations
when external network APIs (RxNav, openFDA, Gemini) fail or time out.
"""
import logging
from typing import List, Dict, Any
from .models import NormalizedDrug, InteractionAlert

logger = logging.getLogger(__name__)

OFFLINE_FALLBACK_RULES = [
    {
        "drugs": {"lisinopril", "spironolactone"},
        "severity": "Severe",
        "description": "Concomitant use may result in severe hyperkalemia. Monitor serum potassium closely.",
        "drug_involved": "Lisinopril + Spironolactone"
    },
    {
        "drugs": {"lisinopril", "ibuprofen"},
        "severity": "Moderate",
        "description": "NSAIDs may decrease the antihypertensive effect of Lisinopril and increase the risk of renal function deterioration.",
        "drug_involved": "Lisinopril + Ibuprofen"
    },
    {
        "drugs": {"metformin", "contrast"},
        "severity": "Moderate",
        "description": "Iodinated contrast media may cause acute renal failure; Metformin must be paused to prevent lactic acidosis.",
        "drug_involved": "Metformin + Contrast"
    },
    {
        "drugs": {"warfarin", "aspirin"},
        "severity": "Severe",
        "description": "Concurrent use significantly increases major bleeding risk. Requires intense INR monitoring.",
        "drug_involved": "Warfarin + Aspirin"
    }
]


class FallbackClinicalProvider:
    """
    Offline circuit breaker evaluating interactions from built-in rules.
    """

    def check_interactions(self, meds: List[NormalizedDrug]) -> List[InteractionAlert]:
        alerts: List[InteractionAlert] = []
        med_set = {m.generic_name.lower().strip() for m in meds if m.generic_name}

        for rule in OFFLINE_FALLBACK_RULES:
            if rule["drugs"].issubset(med_set):
                drugs_list = list(rule["drugs"])
                alerts.append(InteractionAlert(
                    drug_a=drugs_list[0],
                    drug_b=drugs_list[1] if len(drugs_list) > 1 else "",
                    severity=rule["severity"],
                    description=rule["description"],
                    source="Offline Fallback Rules",
                    drug_involved=rule["drug_involved"]
                ))
        return alerts
