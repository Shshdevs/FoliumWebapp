import folium
from folium.plugins import MarkerCluster
from db.database import db


class MapManager:
    def __init__(self, location=None, zoom_start=None):
        self.location = location or self.MAP_CENTER
        self.zoom_start = zoom_start or self.MAP_ZOOM
        self.map = folium.Map(location=self.location, zoom_start=self.zoom_start)
        self.map.get_root().header.add_child(folium.Element(self.CSS_STYLE))
        self.marker_cluster = MarkerCluster(
            name="Маркеры регионов", showCoverageOnHover=False
        ).add_to(self.map)

    @staticmethod
    def _get_class_color(delta, abs_max):
        if delta is None:
            return "#cccccc"
        if abs_max == 0:
            return "#d9ef8b"
            
        step = abs_max / 3
        if delta < -2 * step:
            return "#d73027"  # Темно-красный
        elif delta < -step:
            return "#fc8d59"  # Оранжевый
        elif delta < 0:
            return "#fee08b"  # Желто-оранжевый
        elif delta <= step:
            return "#d9ef8b"  # Светло-зеленый
        elif delta <= 2 * step:
            return "#91cf60"  # Зеленый
        else:
            return "#1a9850"  # Темно-зеленый

    @staticmethod
    def _calculate_abs_max(srf_data):
        return max(
            (
                abs(float(row["delta"]))
                for row in srf_data
                if row.get("delta") is not None
            ),
            default=0,
        )

    @staticmethod
    def _generate_tooltip(name, val, delta):
        val_str = f"{float(val):,.1f}".replace(",", " ") if val is not None else "Нет данных"
        delta_str = f"{float(delta):+,.1f}".replace(",", " ") if delta is not None else "—"
        return f"<b>{name}</b><br>ВРП: {val_str} млн руб.<br>Изменение: {delta_str}"

    @staticmethod
    def _generate_legend_html(abs_max):
        if abs_max == 0:
            abs_max = 1
            
        step = abs_max / 3
        
        def fmt(v):
            return f"{abs(v):,.1f}".replace(",", " ")
            
        classes = [
            {"color": "#1a9850", "label": f"от +{fmt(2*step)} до +{fmt(abs_max)}"},
            {"color": "#91cf60", "label": f"от +{fmt(step)} до +{fmt(2*step)}"},
            {"color": "#d9ef8b", "label": f"от 0 до +{fmt(step)}"},
            {"color": "#fee08b", "label": f"от -{fmt(step)} до 0"},
            {"color": "#fc8d59", "label": f"от -{fmt(2*step)} до -{fmt(step)}"},
            {"color": "#d73027", "label": f"от -{fmt(abs_max)} до -{fmt(2*step)}"},
        ]
        
        legend_items = ""
        for cls in classes:
            legend_items += f'''
            <div style="margin-bottom: 6px; display: flex; align-items: center;">
                <span style="display:inline-block;width:16px;height:16px;background:{cls['color']};border-radius:3px;margin-right:8px;border:1px solid #bbb;"></span>
                <span>{cls['label']}</span>
            </div>
            '''
            
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

    def add_base_regions(self):
        srf_data = db.select("srf", values=self.QUERY_VALUES)
        for srf_object in srf_data:
            geom = srf_object["geom"]
            name = srf_object["name"]
            lat = srf_object["lat"]
            lon = srf_object["lon"]

            if geom:
                folium.GeoJson(geom, tooltip=name).add_to(self.map)
            if lat is not None and lon is not None:
                folium.Marker(location=[lat, lon], tooltip=None, popup=name).add_to(
                    self.marker_cluster
                )
        return self

    def add_vvp_dynamics(self, year: int):
        srf_data = db.execute_fetch(self.VVP_QUERY, [year])
        abs_max = self._calculate_abs_max(srf_data)

        for srf_object in srf_data:
            geom = srf_object["geom"]
            name = srf_object["name"]
            lat = srf_object["lat"]
            lon = srf_object["lon"]
            val = srf_object.get("indicator_value")
            delta = srf_object.get("delta")

            color = self._get_class_color(delta, abs_max)
            tooltip_html = self._generate_tooltip(name, val, delta)

            if geom:
                folium.GeoJson(
                    geom,
                    tooltip=tooltip_html,
                    style_function=lambda x, c=color: {
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

        self.map.get_root().html.add_child(folium.Element(self._generate_legend_html(abs_max)))
        return self

    def render(self) -> str:
        return self.map._repr_html_()

    MAP_CENTER = [61.5240, 105.3188]
    MAP_ZOOM = 3
    CSS_STYLE = "<style>.leaflet-interactive:focus {outline: none;}</style>"
    QUERY_VALUES = "ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.01)) as geom, name, ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon"

    VVP_QUERY = """
    WITH vvp_grouped AS (
        SELECT
            object_name,
            year::integer AS year,
            SUM(indicator_value::numeric) AS indicator_value
        FROM "VVP"
        WHERE indicator_value NOT IN ('-99999999', '-77777777')
        GROUP BY object_name, year::integer
    ),
    vvp_calc AS (
        SELECT
            object_name,
            year,
            indicator_value,
            indicator_value - LAG(indicator_value) OVER (PARTITION BY object_name ORDER BY year) AS delta
        FROM vvp_grouped
    )
    SELECT
        s.name,
        ST_AsGeoJSON(ST_SimplifyPreserveTopology(s.geom, 0.01)) AS geom,
        ST_Y(ST_Centroid(s.geom)) as lat,
        ST_X(ST_Centroid(s.geom)) as lon,
        v.indicator_value,
        v.delta
    FROM "srf" s
    LEFT JOIN vvp_calc v ON s.name = v.object_name AND v.year = %s
    WHERE s.geom IS NOT NULL;
    """
