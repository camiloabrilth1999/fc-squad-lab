from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/.env (ignorado por git), sin depender del CWD. Las variables de entorno le ganan.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_ignore_empty=True, extra="ignore")

    database_url: str = "postgresql+psycopg://fcsl:fcsl@localhost:5544/fcsl"
    http_user_agent: str = Field(
        default="fc-squad-lab/0.1 (uso personal)", validation_alias="FCSL_HTTP_USER_AGENT"
    )
    import_token: str | None = Field(default=None, validation_alias="FCSL_IMPORT_TOKEN")


def get_settings() -> Settings:
    # Se lee en cada llamada para respetar cambios de DATABASE_URL en el entorno.
    return Settings()
