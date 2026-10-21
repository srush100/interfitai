"""
AI model settings: Claude Sonnet 5.5 / Haiku 5.5 by default, no `temperature`
sent (the 5.5 models reject non-default sampling), extra max_tokens room for
thinking, and models switchable through the environment.
"""
import asyncio

import server


class _Capture:
    calls = []

    def __init__(self, **kw):
        self.kw = kw

    def with_model(self, provider, model):
        self.model = model
        return self

    def with_params(self, **params):
        _Capture.calls.append({"model": self.model, **params})
        return self

    async def send_message(self, msg):
        return "{}"


def _run(monkeypatch, fn, **kw):
    _Capture.calls = []
    monkeypatch.setattr(server, "LlmChat", _Capture)
    asyncio.run(fn(system_message="s", user_message="u", **kw))
    return _Capture.calls[0]


def test_sonnet_defaults(monkeypatch):
    c = _run(monkeypatch, server.call_claude_sonnet, temperature=0.2, max_tokens=7000)
    assert c["model"] == "claude-sonnet-5-5"
    assert "temperature" not in c
    assert c["max_tokens"] == 7000 + server.SONNET_THINKING_HEADROOM


def test_haiku_defaults(monkeypatch):
    c = _run(monkeypatch, server.call_claude_haiku, temperature=0.0, max_tokens=400)
    assert c["model"] == "claude-haiku-5-5"
    assert "temperature" not in c
    assert c["max_tokens"] == 400 + server.HAIKU_THINKING_HEADROOM


def test_models_switchable_by_setting(monkeypatch):
    monkeypatch.setattr(server, "CLAUDE_SONNET_MODEL", "claude-sonnet-4-5-20250929")
    assert _run(monkeypatch, server.call_claude_sonnet)["model"] == "claude-sonnet-4-5-20250929"
