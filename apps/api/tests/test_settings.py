from fcsl_api.settings import get_settings


def test_user_agent_default(monkeypatch):
    monkeypatch.delenv("FCSL_HTTP_USER_AGENT", raising=False)
    assert "fc-squad-lab" in get_settings().http_user_agent


def test_user_agent_from_env(monkeypatch):
    monkeypatch.setenv("FCSL_HTTP_USER_AGENT", "mi-agente/9")
    assert get_settings().http_user_agent == "mi-agente/9"
