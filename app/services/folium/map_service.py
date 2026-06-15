from .map_manager import MapManager
from functools import lru_cache


@lru_cache(maxsize=32)
def get_russia_map_html(year: int) -> str:
    return MapManager().add_vvp_dynamics(year).render()
