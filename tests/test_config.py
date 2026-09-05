from aeromind.core.config import get_settings


def test_settings_default_to_safe_mock_mode(monkeypatch) -> None:
    monkeypatch.delenv("AEROMIND_MOCK_MODE", raising=False)
    settings = get_settings()

    assert settings.mock_mode is True
    assert settings.openai_api_key is None
