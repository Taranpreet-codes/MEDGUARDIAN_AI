"""
services/providers/models.py — Data models for Clinical Providers
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class InteractionSeverity(str, Enum):
    CONTRAINDICATED = "Contraindicated"
    SEVERE = "Severe"
    MODERATE = "Moderate"
    MINOR = "Minor"
    SAFE = "Safe"
    UNKNOWN = "Unknown"


@dataclass
class NormalizedDrug:
    input_name: str
    generic_name: str
    rxcui: Optional[str] = None
    brand_names: List[str] = field(default_factory=list)
    confidence_source: str = "local"


@dataclass
class DrugLabelInfo:
    drug_name: str
    generic_name: str
    source: str = "openFDA"
    boxed_warning: Optional[str] = None
    contraindications: Optional[str] = None
    warnings: Optional[str] = None
    drug_interactions: Optional[str] = None
    dosage_and_administration: Optional[str] = None


@dataclass
class InteractionAlert:
    drug_a: str
    drug_b: str
    severity: str  # "Severe", "Moderate", "Minor", "Contraindicated"
    description: str
    mechanism: Optional[str] = None
    clinical_management: Optional[str] = None
    source: str = "Curated Clinical DDI DB"
    fda_label_excerpt: Optional[str] = None
    drug_involved: str = ""

    def __post_init__(self):
        if not self.drug_involved:
            self.drug_involved = f"{self.drug_a.capitalize()} + {self.drug_b.capitalize()}"


@dataclass
class EvidenceCitation:
    source: str
    page: int
    snippet: str
    relevance_score: float = 0.0
    document_id: Optional[str] = None
