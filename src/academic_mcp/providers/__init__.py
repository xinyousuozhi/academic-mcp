from .base import BaseProvider
from .base_kcisa import BaseKCISAProvider, KCISAFieldMapping
from .cinii import CiNiiProvider
from .hgis import HGISProvider
from .kci import KCIProvider
from .kostma import KOSTMAProvider
from .losi import LOSIProvider
from .nl import NLProvider
from .oak import OAKProvider
from .koreantk import KoreanTKProvider
from .nrich import NRICHProvider, NRICH_ENDPOINTS, NRICHEndpoint
from .eyis import EYISProvider
from .gugak import GugakProvider
from .tripitaka import TripitakaProvider
from .folkency import FolkencyProvider
from .stdict import StdictProvider
from .munjip import MunjipProvider
from .itkc import ITKCProvider

__all__ = [
    # Base classes
    "BaseProvider",
    "BaseKCISAProvider",
    "KCISAFieldMapping",
    # NRICH multi-endpoint
    "NRICHProvider",
    "NRICH_ENDPOINTS",
    "NRICHEndpoint",
    # Individual providers
    "CiNiiProvider",
    "HGISProvider",
    "KCIProvider",
    "KOSTMAProvider",
    "LOSIProvider",
    "NLProvider",
    "OAKProvider",
    "KoreanTKProvider",
    "EYISProvider",
    "GugakProvider",
    "TripitakaProvider",
    "FolkencyProvider",
    "StdictProvider",
    "MunjipProvider",
    "ITKCProvider",
]
