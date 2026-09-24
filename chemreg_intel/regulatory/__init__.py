"""Versioned regulatory-source adapters and immutable local snapshots."""

from .adapters.base import SourceAdapter
from .adapters.echa_candidate_list import ECHACandidateListAdapter
from .adapters.echa_annex_xvii import ECHAAnnexXVIIAdapter
from .adapters.eurlex_annex_xvii import EURLexAnnexXVIIReferenceAdapter
from .annex_xvii import AnnexXVIIEngine, AnnexXVIIEntry, RestrictionContext, RestrictionMatchType
from .adapters.echa_clp_annex_vi import ECHACLPAnnexVIAdapter
from .adapters.eurlex_clp_annex_vi import EURLexCLPAnnexVIAdapter
from .clp_annex_vi import CLPAnnexVIEngine, CLPIdentityInput, CLPMatchType, HarmonisedEntry
from .metadata import AuthorityLevel, SourceMetadata, UpdateStatus
from .registry import AdapterRegistry
from .store import DatasetStore

__all__ = [
    "AuthorityLevel",
    "AdapterRegistry",
    "DatasetStore",
    "ECHACandidateListAdapter",
    "ECHAAnnexXVIIAdapter",
    "EURLexAnnexXVIIReferenceAdapter",
    "AnnexXVIIEngine",
    "AnnexXVIIEntry",
    "RestrictionContext",
    "RestrictionMatchType",
    "ECHACLPAnnexVIAdapter",
    "EURLexCLPAnnexVIAdapter",
    "CLPAnnexVIEngine",
    "CLPIdentityInput",
    "CLPMatchType",
    "HarmonisedEntry",
    "SourceAdapter",
    "SourceMetadata",
    "UpdateStatus",
]
