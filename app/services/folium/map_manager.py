import folium
from folium.plugins import MarkerCluster
from db.database import db
from typing import Any, Dict, List, Optional


class MapManager:
    MAP_CENTER = [61.5240, 105.3188]
    MAP_ZOOM = 3
    CSS_STYLE = "<style>.leaflet-interactive:focus {outline: none;}</style>"
    QUERY_VALUES = "ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.01)) as geom, name, ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon"

    def __init__(
        self, location: Optional[list] = None, zoom_start: Optional[int] = None
    ) -> None:
        self.location = location or self.MAP_CENTER
        self.zoom_start = zoom_start or self.MAP_ZOOM
        self.map = folium.Map(location=self.location, zoom_start=self.zoom_start)
        self.map.get_root().header.add_child(folium.Element(self.CSS_STYLE))
        self.marker_cluster = MarkerCluster(
            name="Маркеры регионов", showCoverageOnHover=False
        ).add_to(self.map)

    @staticmethod
    def _format_number(val: Optional[float], show_sign: bool = False) -> str:
        if val is None:
            return "—" if show_sign else "Нет данных"
        fmt_str = f"{float(val):+,.1f}" if show_sign else f"{float(val):,.1f}"
        return fmt_str.replace(",", " ")

    @staticmethod
    def _get_class_color(delta: Optional[float], abs_max: float, step: float) -> str:
        if delta is None:
            return "#cccccc"
        if abs_max == 0:
            return "#d9ef8b"

        if delta < -2 * step:
            return "#d73027"
        if delta < -step:
            return "#fc8d59"
        if delta < 0:
            return "#fee08b"
        if delta <= step:
            return "#d9ef8b"
        if delta <= 2 * step:
            return "#91cf60"
        return "#1a9850"

    @staticmethod
    def _calculate_abs_max(srf_data: List[Dict[str, Any]]) -> float:
        return max(
            (
                abs(float(row.get("delta")))
                for row in srf_data
                if row.get("delta") is not None
            ),
            default=0.0,
        )

    @classmethod
    def _generate_tooltip(
        cls, name: str, val: Optional[float], delta: Optional[float]
    ) -> str:
        val_str = cls._format_number(val)
        delta_str = cls._format_number(delta, show_sign=True)
        return f"<b>{name}</b><br>ВРП: {val_str} млн руб.<br>Изменение: {delta_str}"

    @classmethod
    def _generate_legend_html(cls, abs_max: float) -> str:
        if abs_max == 0:
            abs_max = 1

        step = abs_max / 3

        classes = [
            {
                "color": "#1a9850",
                "label": f"от +{cls._format_number(2 * step)} до +{cls._format_number(abs_max)}",
            },
            {
                "color": "#91cf60",
                "label": f"от +{cls._format_number(step)} до +{cls._format_number(2 * step)}",
            },
            {"color": "#d9ef8b", "label": f"от 0 до +{cls._format_number(step)}"},
            {"color": "#fee08b", "label": f"от -{cls._format_number(step)} до 0"},
            {
                "color": "#fc8d59",
                "label": f"от -{cls._format_number(2 * step)} до -{cls._format_number(step)}",
            },
            {
                "color": "#d73027",
                "label": f"от -{cls._format_number(abs_max)} до -{cls._format_number(2 * step)}",
            },
        ]

        legend_items = "".join(
            f"""
            <div style="margin-bottom: 6px; display: flex; align-items: center;">
                <span style="display:inline-block;width:16px;height:16px;background:{c["color"]};border-radius:3px;margin-right:8px;border:1px solid #bbb;"></span>
                <span>{c["label"]}</span>
            </div>
            """
            for c in classes
        )

        return f"""
        <div style="position:fixed;bottom:40px;left:20px;z-index:9999;background:white;padding:14px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,.35);font-size:13px;width:280px;font-family:Arial,sans-serif;">
            <b style="display:block;margin-bottom:10px;">Динамика ВРП (млн руб.)</b>
            {legend_items}
            <div style="margin-top: 12px; font-size: 12px; color: #555; border-top: 1px solid #ddd; padding-top: 10px; display: flex; align-items: center;">
                <span style="display:inline-block;width:14px;height:14px;background:#cccccc;border-radius:3px;margin-right:8px;border:1px solid #bbb;"></span> 
                Нет данных / 1-й год
            </div>
        </div>
        """

    def _generate_panel(self, current_year: int) -> None:
        try:
            years = db.execute_fetch(
                'SELECT MIN(year::integer) as min_y, MAX(year::integer) as max_y FROM "VVP"'
            )[0]
            min_year = years["min_y"] or 2000
            max_year = years["max_y"] or 2022
        except Exception:
            min_year, max_year = 2000, 2022

        panel_html = f"""
        <div style="position:fixed;top:20px;right:20px;z-index:9999;background:white;padding:15px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,.35);font-family:Arial,sans-serif;width:280px;">
            <div style="margin-bottom:10px;font-size:16px;font-weight:bold;">
                Год: <span id="year-display">{current_year}</span>
            </div>
            <input
                type="range"
                id="year-slider"
                min="{min_year}"
                max="{max_year}"
                value="{current_year}"
                step="1"
                style="width:100%;cursor:pointer;"
            />
            <style>
                #year-slider {{
                    -webkit-appearance: none;
                    appearance: none;
                    height: 8px;
                    border-radius: 4px;
                    background: #e0e0e0;
                    outline: none;
                }}
                #year-slider::-webkit-slider-thumb {{
                    -webkit-appearance: none;
                    appearance: none;
                    width: 18px;
                    height: 18px;
                    border-radius: 50%;
                    background: #007bff;
                    cursor: pointer;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
                }}
                #year-slider::-moz-range-thumb {{
                    width: 18px;
                    height: 18px;
                    border-radius: 50%;
                    background: #007bff;
                    cursor: pointer;
                    border: none;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
                }}
            </style>
            <script>
                const yearSlider = document.getElementById("year-slider");
                const yearDisplay = document.getElementById("year-display");

                function updateSliderColor() {{
                    const min = yearSlider.min || 0;
                    const max = yearSlider.max || 100;
                    const val = yearSlider.value;
                    const percentage = ((val - min) / (max - min)) * 100;
                    yearSlider.style.background = `linear-gradient(to right, #007bff ${{percentage}}%, #e0e0e0 ${{percentage}}%)`;
                }}

                yearSlider.addEventListener("input", (event) => {{
                    yearDisplay.textContent = event.target.value;
                    updateSliderColor();
                }});

                yearSlider.addEventListener("change", (event) => {{
                    const selectedYear = event.target.value;
                    // Отправляем сообщение родительскому окну при изменении ползунка
                    window.parent.postMessage({{ type: 'updateYear', year: selectedYear }}, '*');
                }});

                updateSliderColor();
            </script>
        </div>
        """
        self.map.get_root().html.add_child(folium.Element(panel_html))

    def add_base_regions(self) -> "MapManager":
        srf_data = db.select("srf", values=self.QUERY_VALUES)
        for srf_object in srf_data:
            geom = srf_object.get("geom")
            name = srf_object.get("name")
            lat = srf_object.get("lat")
            lon = srf_object.get("lon")

            if geom:
                folium.GeoJson(geom, tooltip=name).add_to(self.map)
            if lat is not None and lon is not None:
                folium.Marker(location=[lat, lon], tooltip=None, popup=name).add_to(
                    self.marker_cluster
                )
        return self

    def add_vvp_dynamics(self, year: int) -> "MapManager":
        srf_data = db.select(
            table="vvp_map_view",
            values="name, geom, lat, lon, indicator_value, delta",
            eq=[("year", year)],
        )
        abs_max = self._calculate_abs_max(srf_data)
        step = abs_max / 3

        for srf_object in srf_data:
            geom = srf_object.get("geom")
            name = srf_object.get("name", "Неизвестно")
            lat = srf_object.get("lat")
            lon = srf_object.get("lon")
            val = srf_object.get("indicator_value")
            delta = srf_object.get("delta")

            color = self._get_class_color(delta, abs_max, step)
            tooltip_html = self._generate_tooltip(name, val, delta)

            if geom:
                folium.GeoJson(
                    geom,
                    tooltip=tooltip_html,
                    style_function=lambda _, c=color: {
                        "fillColor": c,
                        "color": "black",
                        "weight": 1,
                        "fillOpacity": 0.75,
                    },
                ).add_to(self.map)
            if lat is not None and lon is not None:
                folium.Marker(location=[lat, lon], tooltip=tooltip_html).add_to(
                    self.marker_cluster
                )

        self.map.get_root().html.add_child(
            folium.Element(self._generate_legend_html(abs_max))
        )
        self._generate_panel(year)
        return self

    def render(self) -> str:
        return self.map._repr_html_()
