from .map_manager import MapManager
from functools import lru_cache

@lru_cache(maxsize=1)
def get_russia_map_html() -> str:
    return MapManager().add_base_regions().render()
