import json
import psycopg2
import pandas as pd
import folium
from folium.plugins import TimeSliderChoropleth
from flask import Flask

MISSING_VALUES = {-99999999, -77777777}

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "InnerNationalProduct",
    "user": "postgres",
    "password": "12345",
}

app = Flask(__name__)


def fetch_data():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        SELECT name, ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.01)) AS geom
        FROM "srf"
        WHERE geom IS NOT NULL
    """)
    geo_df = pd.DataFrame(cur.fetchall(), columns=["full_name", "geom"])

    cur.execute("""
        SELECT
            v.object_name,
            v.year::integer                                             AS year,
            v.indicator_value::numeric                                  AS indicator_value,
            v.indicator_value::numeric
                - LAG(v.indicator_value::numeric)
                  OVER (PARTITION BY v.object_name ORDER BY v.year::integer)
                                                                        AS delta
        FROM "VVP" v
        WHERE v.indicator_value NOT IN ('-99999999', '-77777777')
        
        ORDER BY v.object_name, v.year::integer
    """)
    vrp_df = pd.DataFrame(
        cur.fetchall(), columns=["object_name", "year", "indicator_value", "delta"]
    )

    conn.close()

    vrp_df["indicator_value"] = pd.to_numeric(
        vrp_df["indicator_value"], errors="coerce"
    )
    vrp_df["delta"] = pd.to_numeric(vrp_df["delta"], errors="coerce")
    vrp_df["year"] = pd.to_numeric(vrp_df["year"], errors="coerce").astype("Int64")
    vrp_df = vrp_df.dropna(subset=["indicator_value", "year"])

    return geo_df, vrp_df


def dynamic_color(delta, abs_max):
    """Красный (снижение) → жёлтый (0) → зелёный (рост)."""
    if delta is None or (isinstance(delta, float) and pd.isna(delta)):
        return "#cccccc"
    if abs_max == 0:
        return "#ffff00"
    t = max(-1.0, min(1.0, float(delta) / abs_max))
    if t < 0:
        s = abs(t)
        r = int(255)
        g = int(255 * (1 - s))
        b = 0
        # жёлтый → красный
        r = 255
        g = int(255 * (1 - s))
        b = 0
    elif t > 0:
        s = t
        # жёлтый → зелёный
        r = int(255 * (1 - s))
        g = 200
        b = 0
    else:
        return "#ffff00"
    return f"#{r:02x}{g:02x}{b:02x}"


def build_map(geo_df, vrp_df):
    # Агрегируем дубли (регион + год)
    vrp_agg = vrp_df.groupby(["object_name", "year"], as_index=False).agg(
        indicator_value=("indicator_value", "sum"), delta=("delta", "first")
    )

    years = sorted(vrp_agg["year"].unique().tolist())
    abs_max = float(vrp_agg["delta"].abs().max(skipna=True))

    # GeoJSON
    features = []
    valid_names = []
    for _, row in geo_df.iterrows():
        try:
            geom = json.loads(row["geom"])
        except Exception:
            continue
        features.append(
            {
                "type": "Feature",
                "id": str(len(features)),
                "properties": {"name": row["full_name"]},
                "geometry": geom,
            }
        )
        valid_names.append(row["full_name"])

    geojson = {"type": "FeatureCollection", "features": features}
    name_to_fid = {name: str(i) for i, name in enumerate(valid_names)}

    # styledict для TimeSliderChoropleth
    styledict = {}
    for name, fid in name_to_fid.items():
        region_ts = {}
        for year in years:
            ts = str(int(pd.Timestamp(f"{int(year)}-01-01").timestamp()))
            subset = vrp_agg[
                (vrp_agg["object_name"] == name) & (vrp_agg["year"] == year)
            ]
            if not subset.empty:
                delta = subset["delta"].iloc[0]
                color = dynamic_color(delta if pd.notna(delta) else None, abs_max)
            else:
                color = "#cccccc"
            region_ts[ts] = {"color": color, "opacity": 0.85}
        styledict[fid] = region_ts

    m = folium.Map(location=[62, 95], zoom_start=3, tiles="CartoDB positron")

    TimeSliderChoropleth(
        data=geojson,
        styledict=styledict,
        name="Динамика ВРП",
    ).add_to(m)

    # Легенда
    legend_html = """
    <div style="position:fixed;bottom:40px;left:20px;z-index:9999;background:white;
                padding:10px 14px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,.35);
                font-size:13px;font-family:Arial;line-height:22px;">
      <b>Динамика ВРП (к пред. году)</b><br>
      <span style="display:inline-block;width:16px;height:16px;background:#00c800;
                   border-radius:3px;vertical-align:middle;margin-right:6px;"></span>Рост<br>
      <span style="display:inline-block;width:16px;height:16px;background:#ffff00;
                   border-radius:3px;vertical-align:middle;margin-right:6px;border:1px solid #ccc;"></span>Без изменений<br>
      <span style="display:inline-block;width:16px;height:16px;background:#ff0000;
                   border-radius:3px;vertical-align:middle;margin-right:6px;"></span>Снижение<br>
      <span style="display:inline-block;width:16px;height:16px;background:#cccccc;
                   border-radius:3px;vertical-align:middle;margin-right:6px;"></span>Нет данных / 1-й год
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Тултип: ВРП + динамика за каждый год
    pivot_val = vrp_agg.pivot(
        index="object_name", columns="year", values="indicator_value"
    )
    pivot_delta = vrp_agg.pivot(index="object_name", columns="year", values="delta")

    tooltip_features = []
    for feat in features:
        name = feat["properties"]["name"]
        props = {"name": name}
        for yr in years:
            val = (
                pivot_val.loc[name, yr]
                if (name in pivot_val.index and yr in pivot_val.columns)
                else None
            )
            delta = (
                pivot_delta.loc[name, yr]
                if (name in pivot_delta.index and yr in pivot_delta.columns)
                else None
            )
            props[f"v{int(yr)}"] = (
                f"{val:,.1f}" if val is not None and pd.notna(val) else "—"
            )
            props[f"d{int(yr)}"] = (
                f"{delta:+,.1f}" if delta is not None and pd.notna(delta) else "—"
            )
        tooltip_features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": feat["geometry"],
            }
        )

    all_fields = ["name"]
    all_aliases = ["Регион:"]
    for yr in years:
        all_fields += [f"v{int(yr)}", f"d{int(yr)}"]
        all_aliases += [f"ВРП {int(yr)} (млн руб.):", f"Δ к {int(yr) - 1}:"]

    folium.GeoJson(
        {"type": "FeatureCollection", "features": tooltip_features},
        style_function=lambda _: {
            "fillOpacity": 0,
            "weight": 0,
            "color": "transparent",
        },
        tooltip=folium.GeoJsonTooltip(
            fields=all_fields,
            aliases=all_aliases,
            localize=True,
            sticky=True,
        ),
        name="Подсказки",
    ).add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)

    return m._repr_html_()


@app.route("/")
def index():
    geo_df, vrp_df = fetch_data()
    html = build_map(geo_df, vrp_df)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Динамика ВРП регионов России</title>
  <style>html, body {{ margin: 0; padding: 0; height: 100%; }}</style>
</head>
<body style="margin:0;padding:0;height:100%;">
  {html}
</body>
</html>"""


if __name__ == "__main__":
    print("Сервер запущен: http://localhost:4040")
    app.run(host="0.0.0.0", port=4040, debug=True)
