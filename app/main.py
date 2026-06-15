from flask import Flask
from core.config import config
from api.routes.map_router import map_bp
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


def create_app():
    app = Flask(__name__)
    app.register_blueprint(map_bp)

    app.logger.info("Flask application initialized and starting up.")
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=config.HOST, port=config.PORT, debug=True)
