from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    DB_URL = os.getenv("DATABASE_URL")
    PORT = os.getenv("PORT")
    HOST = os.getenv("HOST")
    TEMPLATES_DIR = os.getenv("TEMPLATES_DIR")


config = Config()
