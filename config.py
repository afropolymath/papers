import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    DEBUG = True
    TESTING = False
    UPLOAD_FOLDER = "upload/"
    MAX_CONTENT_PATH = 26214400
    DATABASE_HOST = os.getenv("DATABASE_HOST")
    DATABASE_PORT = os.getenv("DATABASE_PORT")
    DATABASE_NAME = os.getenv("DATABASE_NAME")


class DevelopmentConfig(Config):
    SECRET_KEY = "S0m3S3cr3tK3y"


config = {
    "development": DevelopmentConfig,
    "testing": DevelopmentConfig,
    "production": DevelopmentConfig,
}
