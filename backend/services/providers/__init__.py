"""
services/providers/__init__.py — Provider Architecture Package
"""
from .models import (
    NormalizedDrug,
    DrugLabelInfo,
    InteractionSeverity,
    InteractionAlert,
    EvidenceCitation,
)
from .base import (
    BaseNormalizationProvider,
    BaseClinicalLabelProvider,
    BaseInteractionProvider,
    BaseEvidenceProvider,
)
from .rxnav_normalizer import RxNavNormalizerProvider
from .openfda_provider import OpenFDALabelProvider
from .curated_ddi_provider import CuratedDDIProvider
from .composite_interaction_provider import CompositeInteractionProvider
from .chroma_provider import ChromaGuidelineProvider
from .fallback_provider import FallbackClinicalProvider

__all__ = [
    "NormalizedDrug",
    "DrugLabelInfo",
    "InteractionSeverity",
    "InteractionAlert",
    "EvidenceCitation",
    "BaseNormalizationProvider",
    "BaseClinicalLabelProvider",
    "BaseInteractionProvider",
    "BaseEvidenceProvider",
    "RxNavNormalizerProvider",
    "OpenFDALabelProvider",
    "CuratedDDIProvider",
    "CompositeInteractionProvider",
    "ChromaGuidelineProvider",
    "FallbackClinicalProvider",
]
