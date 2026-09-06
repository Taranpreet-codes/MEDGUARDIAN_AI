"""
services/providers/base.py — Abstract Base Classes for Clinical Providers
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from .models import NormalizedDrug, DrugLabelInfo, InteractionAlert, EvidenceCitation


class BaseNormalizationProvider(ABC):
    """Abstract provider for drug name normalization and RxCUI resolution."""

    @abstractmethod
    def normalize(self, drug_name: str) -> NormalizedDrug:
        """Normalizes an input medication name to canonical generic name and RxCUI."""
        pass


class BaseClinicalLabelProvider(ABC):
    """Abstract provider for official drug package insert warnings and contraindications."""

    @abstractmethod
    def get_label_info(self, generic_name: str) -> Optional[DrugLabelInfo]:
        """Fetches official drug label contraindications, boxed warnings, and warnings."""
        pass


class BaseInteractionProvider(ABC):
    """Abstract provider for drug-drug interaction evaluation."""

    @abstractmethod
    def check_interactions(self, meds: List[NormalizedDrug]) -> List[InteractionAlert]:
        """Checks for drug-drug interactions among a list of normalized medications."""
        pass


class BaseEvidenceProvider(ABC):
    """Abstract provider for clinical guideline retrieval and evidence citation."""

    @abstractmethod
    def retrieve_evidence(self, query: str, limit: int = 3) -> List[EvidenceCitation]:
        """Retrieves grounded clinical evidence documents with relevance scores."""
        pass
