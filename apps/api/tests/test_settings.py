from fcsl_api.settings import Settings, get_settings


def test_user_agent_default(monkeypatch):
    monkeypatch.delenv("FCSL_HTTP_USER_AGENT", raising=False)
    assert "fc-squad-lab" in get_settings().http_user_agent


def test_user_agent_from_env(monkeypatch):
    monkeypatch.setenv("FCSL_HTTP_USER_AGENT", "mi-agente/9")
    assert get_settings().http_user_agent == "mi-agente/9"


def test_env_file_is_apps_api_dotenv():
    from fcsl_api import settings

    assert settings.ENV_FILE == settings.Path(__file__).resolve().parents[1] / ".env"


def test_reads_import_token_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("FCSL_IMPORT_TOKEN", raising=False)
    monkeypatch.delenv("FCSL_HTTP_USER_AGENT", raising=False)
    env = tmp_path / ".env"
    env.write_text("FCSL_IMPORT_TOKEN=desde-archivo\nFCSL_HTTP_USER_AGENT=agente-archivo/1\n")
    s = Settings(_env_file=env)
    assert (s.import_token, s.http_user_agent) == ("desde-archivo", "agente-archivo/1")


def test_environment_wins_over_env_file(monkeypatch, tmp_path):
    monkeypatch.setenv("FCSL_IMPORT_TOKEN", "del-entorno")
    env = tmp_path / ".env"
    env.write_text("FCSL_IMPORT_TOKEN=desde-archivo\n")
    assert Settings(_env_file=env).import_token == "del-entorno"


def test_empty_value_in_env_file_means_no_token(monkeypatch, tmp_path):
    monkeypatch.delenv("FCSL_IMPORT_TOKEN", raising=False)
    env = tmp_path / ".env"
    env.write_text("FCSL_IMPORT_TOKEN=\n")
    assert not Settings(_env_file=env).import_token


def test_tests_ignore_the_real_env_file():
    assert Settings.model_config.get("env_file") is None


def test_example_env_file_keeps_defaults(monkeypatch):
    """Copiar .env.example tal cual (valores vacíos) no deja el User-Agent vacío."""
    from fcsl_api import settings

    monkeypatch.delenv("FCSL_IMPORT_TOKEN", raising=False)
    monkeypatch.delenv("FCSL_HTTP_USER_AGENT", raising=False)
    s = Settings(_env_file=settings.ENV_FILE.with_name(".env.example"))
    assert "fc-squad-lab" in s.http_user_agent
    assert s.import_token is None
