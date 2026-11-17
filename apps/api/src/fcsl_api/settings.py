from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fcsl:fcsl@localhost:5544/fcsl"


def get_settings() -> Settings:
    # Se lee en cada llamada para respetar cambios de DATABASE_URL en el entorno.
    return Settings()
