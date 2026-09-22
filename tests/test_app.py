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
    assert body["prep"] is not None  # opponents present + stage >= 2
    assert {o["name"] for o in body["next_opponents"]} == {"RivalOne", "RivalTwo"}
    assert body["comps"][0]["positioning"]["frontline"]
    top = body["comps"][0]
    # '4-cost carry' is on the board, so it must not appear in missing_units
    assert all(m["unit"] != "4-cost carry" for m in top["missing_units"])
    assert top["units"]  # full roster is exposed for the overlay comp view
    assert top["carry_items"]


def test_advice_shop_marks_carry_core_and_pair(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post(
        "/advice",
        json={
            "state": {
                "stage": "4-1",
                "board": [{"name": "4-cost carry"}, {"name": "support unit"}],
                "shop": ["4-cost carry", "4-cost tank", "support unit", "unrelated unit"],
            }
        },
    )
    assert resp.status_code == 200
    marks = {m["unit"]: m["reason"] for m in resp.json()["shop"]}
    assert marks.get("4-cost carry") == "carry"
    assert marks.get("4-cost tank") == "core"
    assert marks.get("support unit") in {"core", "pair"}
    assert "unrelated unit" not in marks


def test_next_opponents_respects_fought_history(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post(
        "/advice",
        json={
            "state": {
                "stage": "3-4",
                "opponents": [
                    {"name": "Alpha", "units": [{"name": "4-cost carry"}, {"name": "4-cost tank"}]},
                    {"name": "Beta", "units": [{"name": "x"}]},
                    {"name": "Gamma", "units": [{"name": "y"}]},
                ],
                "fought_opponents": ["Alpha"],
            }
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    names = {o["name"] for o in body["next_opponents"]}
    assert "Alpha" not in names  # just fought -> excluded from next cycle
    assert names == {"Beta", "Gamma"}
    assert body["last_fought"] == "Alpha"


def test_advice_survives_malformed_stage(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post(
        "/advice",
        json={
            "state": {
                "stage": "x-y",
                "level": 7,
                "board": [{"name": "4-cost carry"}],
            }
        },
    )
    assert resp.status_code == 200
    assert "comps" in resp.json()


def test_advice_top_n_zero_returns_no_comps(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post("/advice", json={"state": {}, "top_n": 0})
    assert resp.status_code == 200
    assert resp.json()["comps"] == []


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


def test_custom_comp_crud_roundtrip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    monkeypatch.setenv("TFT_CUSTOM_COMPS", str(tmp_path / "custom.json"))
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    created = client.post(
        "/comps",
        json={
            "name": "My Homebrew",
            "units": ["my unit a", "my unit b"],
            "carry_items": {"my unit a": ["item x"]},
            "positioning": {"frontline": ["my unit b"], "backline": ["my unit a"]},
        },
    )
    assert created.status_code == 201
    slug = created.json()["slug"]
    assert slug == "my-homebrew"

    listed = client.get("/comps").json()["comps"]
    assert any(c["slug"] == "my-homebrew" for c in listed)

    # the custom comp is part of the advice criteria set
    resp = client.post(
        "/advice",
        json={"state": {"board": [{"name": "my unit a"}, {"name": "my unit b"}]}},
    )
    assert resp.status_code == 200
    assert any(c["slug"] == "my-homebrew" for c in resp.json()["comps"])

    deleted = client.delete(f"/comps/{slug}")
    assert deleted.status_code == 200
    assert not any(
        c["slug"] == "my-homebrew" for c in client.get("/comps").json()["comps"]
    )
    assert client.delete(f"/comps/{slug}").status_code == 404


def test_create_comp_requires_name(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    monkeypatch.setenv("TFT_CUSTOM_COMPS", str(tmp_path / "custom.json"))
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    assert client.post("/comps", json={"name": "  "}).status_code == 422


def test_itemization_fields_and_carousel_pick(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post(
        "/advice",
        json={
            "state": {
                "stage": "3-2",
                "board": [{"name": "4-cost carry"}],
                "items": ["spare component"],
                "carousel_items": ["hp item", "bis 1", "unrelated item"],
            }
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["slam"] is not None  # bench has items -> slam question fires
    top = body["comps"][0]
    assert top["tank_items"]
    assert top["item_priority"]
    assert top["item_holders"]
    assert top["item_plan"]
    car = body["carousel"]
    assert car is not None
    assert car["item"] == "bis 1"  # highest item_priority match on the wheel
    assert car["rank"] == 1


def test_carousel_absent_without_wheel_data(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post("/advice", json={"state": {"stage": "3-2"}})
    assert resp.status_code == 200
    assert resp.json()["carousel"] is None


def test_post_fight_and_opponent_health(monkeypatch) -> None:
    monkeypatch.setenv("TFT_ENGINE", "mock")
    _engine.cache_clear()
    _library.cache_clear()

    client = TestClient(create_app())
    resp = client.post(
        "/advice",
        json={
            "state": {
                "stage": "3-2",
                "last_result": "defeat",
                "opponents": [{"name": "rival", "health": 60, "xp": 6}],
            }
        },
    )
    assert resp.status_code == 200
    assert resp.json()["post_fight"] is not None
