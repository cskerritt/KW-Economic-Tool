"""Life care plan cost projection via the DED Medical Care Cost Index method."""

from engine.lcp.growth import medical_growth_rate, real_medical_inflation
from engine.lcp.projection import (
    LCPItem,
    LCPItemResult,
    LCPResult,
    project_lcp,
)

__all__ = [
    "medical_growth_rate",
    "real_medical_inflation",
    "LCPItem",
    "LCPItemResult",
    "LCPResult",
    "project_lcp",
]
