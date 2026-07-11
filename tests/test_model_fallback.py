import importlib

from pydantic_ai.models.fallback import FallbackModel

agent_module = importlib.import_module("agent.agent")


def _reset_model_cache(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "_cached_model", None)
    for name in (
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GITHUB_MODELS_TOKEN",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_google_configures_primary_and_same_key_fallback(monkeypatch):
    _reset_model_cache(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")

    model = agent_module.get_model()

    assert isinstance(model, FallbackModel)
    assert [configured.model_name for configured in model.models] == [
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite",
    ]


def test_github_models_is_added_as_tertiary_fallback(monkeypatch):
    _reset_model_cache(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("GITHUB_MODELS_TOKEN", "github_pat_test")

    model = agent_module.get_model()

    assert isinstance(model, FallbackModel)
    assert [configured.model_name for configured in model.models] == [
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite",
        "openai/gpt-4.1",
    ]


def test_transient_capacity_errors_are_retried():
    for message in (
        "429 RESOURCE_EXHAUSTED",
        "503 UNAVAILABLE: high demand",
        "504 DEADLINE_EXCEEDED",
    ):
        assert agent_module._is_transient_model_error(RuntimeError(message))


def test_authentication_errors_are_not_retried():
    assert not agent_module._is_transient_model_error(RuntimeError("401 invalid key"))


def test_matchmaking_prompt_broadens_preferences_to_core_interest():
    assert "core interest" in agent_module.SYSTEM_PROMPT
    assert (
        'retry with the core interest alone (e.g. "volunteering")'
        in agent_module.SYSTEM_PROMPT
    )
    assert "day/time as preferences" in agent_module.SYSTEM_PROMPT
