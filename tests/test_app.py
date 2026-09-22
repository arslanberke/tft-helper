import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service"))

from fastapi.testclient import TestClient  # noqa: E402
from tft_advisor.app import _engine, _library, create_app  # noqa: E402


def test_advice_end_to_end_with_mock_engine(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post(
        "/advice",
        json={
            "state": {
                "stage": "4-2",
                "level": 7,
                "gold": 52,
                "hp": 60,
                "board": [{"name": "4-cost carry", "star": 2, "items": ["bis 1"]}],
                "offered_augments": ["econ augment", "combat augment", "trait emblem augment"],
                "opponents": [
                    {
                        "name": "RivalOne",
                        "units": [
                            {"name": "4-cost carry"},
                            {"name": "4-cost tank"},
                            {"name": "unrelated unit"},
                        ],
                    },
                    {"name": "RivalTwo", "units": [{"name": "unrelated unit"}]},
                ],
            }
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["engines"] == ["mock"]
    assert 1 <= len(body["comps"]) <= 3
    assert all(0.0 <= c["probability"] <= 1.0 for c in body["comps"])
    assert body["econ"]["action"] in {"roll", "level", "hold"}
    assert body["augment"]["pick"] in {
        "econ augment",
        "combat augment",
        "trait emblem augment",
    }
    assert body["pivot"] is not None


def test_contested_count_flags_shared_cores() -> None:
    from tft_advisor.comps import contested_count

    opponents = [["4-cost carry", "4-cost tank", "other"], ["other", "also other"]]
    assert contested_count(["4-cost carry", "4-cost tank"], opponents) == 1
    assert contested_count(["low-cost carry"], opponents) == 0
    assert contested_count(["other"], opponents, min_overlap=1) == 2


def test_health_reports_mock_engine(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["engines"] == ["mock"]
