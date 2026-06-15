from flask import render_template, Blueprint, request
from services.folium.map_service import get_russia_map_html
from db.database import db

map_bp = Blueprint("map", __name__)


@map_bp.route("/")
def index():
    try:
        years = db.execute_fetch(
            'SELECT MIN(year::integer) as min_y, MAX(year::integer) as max_y FROM "VVP"'
        )[0]
        min_year = years["min_y"] or 2000
        max_year = years["max_y"] or 2022
    except Exception:
        min_year, max_year = 2000, 2022

    map_html = get_russia_map_html(max_year)
    return render_template(
        "index.html", map_html=map_html, min_year=min_year, max_year=max_year
    )


@map_bp.route("/map")
def get_map():
    selected_year = request.args.get("year", type=int, default=2022)
    return get_russia_map_html(selected_year)
