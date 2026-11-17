from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fcsl:fcsl@localhost:5544/fcsl"
    http_user_agent: str = Field(
        default="fc-squad-lab/0.1 (uso personal)", validation_alias="FCSL_HTTP_USER_AGENT"
    )


def get_settings() -> Settings:
    # Se lee en cada llamada para respetar cambios de DATABASE_URL en el entorno.
    return Settings()
