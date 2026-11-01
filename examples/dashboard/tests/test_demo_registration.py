import importlib.util
from pathlib import Path
from types import SimpleNamespace


def test_registration_sends_configured_key_without_saving_it(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "install_reference_sources.py"
    spec = importlib.util.spec_from_file_location("reference_registration", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    class Session:
        headers = {}

        def get(self, url, **kwargs):
            calls.append((url, dict(self.headers)))
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"success": True, "data": []},
            )

    monkeypatch.setenv("DBGPT_API_KEY", "test-key")
    monkeypatch.setattr(module.requests, "Session", Session)
    module.register_sources([], tmp_path, "http://localhost:5670", "alice")
    assert calls == [
        (
            "http://localhost:5670/api/v2/serve/datasources",
            {"Authorization": "Bearer test-key", "User-Id": "alice"},
        )
    ]
    assert not list(tmp_path.iterdir())
