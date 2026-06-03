import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    @staticmethod
    def get_database_url():
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise EnvironmentError(
                "DATABASE_URL environment variable is not set. "
                "Please set it in your .env file or environment."
            )
        # Normalise legacy URL schemes
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return self.get_database_url()


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = "DEBUG"


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    LOG_LEVEL = "WARNING"

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        return "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    cfg_class = config_map.get(env, DevelopmentConfig)
    return cfg_class()
