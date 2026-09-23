from __future__ import annotations

import argparse
import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .comps import (
    Comp,
    PivotOption,
    SourceRating,
    contested_count,
    entry_signals,
    load_library,
    pivot_candidates,
)
from .engines import Engine, FusedAnswer, build_default_engine
from .odds import pool_from_state, roll_window
from .questions import FLEX_SLUG, build_questions
from .scout import available as scout_available
from .scout import scout_board
from .sources.base import slugify
from .state import GameState

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_LIBRARY = DATA_DIR / "comps.json"
DEFAULT_CUSTOM = DATA_DIR / "custom_comps.json"


class AdviceRequest(BaseModel):
    state: GameState
    top_n: int = 3


class CompAdvice(BaseModel):
    slug: str
    name: str
    probability: float
    agreement: bool
    contested: int = 0  # opponents sharing >=2 core units
    entry: dict = Field(default_factory=dict)  # play-conditions match: score/matched/missing
    pivot_to: list[PivotOption] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)  # meta-site placement stats
    roll: dict = Field(default_factory=dict)  # shop-odds roll window for key units
    positioning: dict = Field(default_factory=dict)  # frontline/backline/notes
    missing_units: list[dict] = Field(default_factory=list)  # absent cores + substitutes
    endgame: str = ""
    units: list[str] = Field(default_factory=list)  # full comp roster
    carry_items: dict[str, list[str]] = Field(default_factory=dict)
    tank_items: dict[str, list[str]] = Field(default_factory=dict)
    item_priority: list[str] = Field(default_factory=list)
    item_holders: dict[str, list[str]] = Field(default_factory=dict)
    item_plan: str = ""


class ShopMark(BaseModel):
    unit: str
    reason: str  # carry | core | pair


class NextOpponent(BaseModel):
    name: str
    shared: int = 0  # core units shared with the top recommended comp
    units_known: int = 0


class AdviceResponse(BaseModel):
    comps: list[CompAdvice]
    econ: dict | None = None
    augment: dict | None = None
    pivot: float | None = None
    prep: float | None = None
    slam: float | None = None
    post_fight: float | None = None
    carousel: dict | None = None  # best pick from the carousel wheel, if known
    shop: list[ShopMark] = Field(default_factory=list)
    next_opponents: list[NextOpponent] = Field(default_factory=list)
    rival_names: list[str] = Field(default_factory=list)
    last_fought: str = ""
    engines: list[str]
    stage: str
    level: int = 0


class ScoutToggle(BaseModel):
    enabled: bool


class CompIn(BaseModel):
    """Payload for user-created comps (from the overlay's builder UI)."""

    name: str
    units: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    carry_items: dict[str, list[str]] = Field(default_factory=dict)
    conditions: dict = Field(default_factory=dict)
    strategy: str = ""
    positioning: dict = Field(default_factory=dict)
    unit_costs: dict[str, int] = Field(default_factory=dict)


@lru_cache
def _engine() -> Engine:
    return build_default_engine()


def _custom_path() -> Path:
    return Path(os.environ.get("TFT_CUSTOM_COMPS", DEFAULT_CUSTOM))


def _read_custom() -> list[Comp]:
    path = _custom_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    return [Comp.model_validate(c) for c in data.get("comps", [])]


def _write_custom(comps: list[Comp]) -> None:
    path = _custom_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"comps": [c.model_dump() for c in comps]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)
    _library.cache_clear()


@lru_cache
def _library() -> list[Comp]:
    path = Path(os.environ.get("TFT_COMPS", DEFAULT_LIBRARY))
    comps = load_library(path)
    by_slug = {c.slug: c for c in comps}
    for custom in _read_custom():
        by_slug[custom.slug] = custom  # user comps win on slug collision
    return list(by_slug.values())


def _unit_names(units) -> set[str]:
    return {u.name.lower() for u in units if u.name}


def _shop_marks(state: GameState, top: Comp | None) -> list[ShopMark]:
    """Which shop slots to grab: carries and core units of the top comp,
    plus pairs for units already on the board/bench (cheap upgrades)."""
    if not state.shop:
        return []
    owned = _unit_names(state.board) | _unit_names(state.bench)
    core = {u.lower() for u in top.units} if top else set()
    carries = {c.lower() for c in top.carry_items} if top else set()
    marks: list[ShopMark] = []
    for raw in state.shop:
        name = str(raw).strip()
        key = name.lower()
        if not key:
            continue
        if key in carries:
            reason = "carry"
        elif key in core:
            reason = "core"
        elif key in owned:
            reason = "pair"
        else:
            continue
        marks.append(ShopMark(unit=name, reason=reason))
    return marks


def _carousel_pick(state: GameState, top: Comp | None) -> dict | None:
    """Best item to take off the carousel wheel: the comp's item_priority
    ranks the options; pairs for owned units are the fallback signal."""
    if not state.carousel_items:
        return None
    priority = [p.lower() for p in (top.item_priority if top else [])]

    def rank(item: str) -> int:
        key = item.lower()
        for i, p in enumerate(priority):
            if p in key or key in p:
                return i
        return len(priority)

    best = min(state.carousel_items, key=rank)
    idx = rank(best)
    return {
        "item": best,
        "rank": idx + 1 if idx < len(priority) else None,
        "options": list(state.carousel_items),
    }


def create_app() -> FastAPI:
    app = FastAPI(title="TFT Comp Advisor")

    @app.get("/health")
    def health() -> dict:
        engine = _engine()
        engines = (
            [e.name for e in engine.engines]
            if hasattr(engine, "engines")
            else [engine.name]
        )
        return {"ok": True, "engines": engines, "comps": len(_library())}

    # Screen-reading auto-scan is opt-in: the risky path (Riot policy) can be
    # toggled at runtime; manual scout notes always keep working.
    scout_enabled = os.environ.get("TFT_SCOUT", "1") != "0"

    @app.get("/scout/status")
    def scout_status() -> dict:
        return {"enabled": scout_enabled, "available": scout_available()}

    @app.post("/scout/toggle")
    def scout_toggle(req: ScoutToggle) -> dict:
        nonlocal scout_enabled
        scout_enabled = bool(req.enabled)
        return {"enabled": scout_enabled, "available": scout_available()}

    @app.post("/scout")
    def scout() -> dict:
        """Screen-scout the rival board currently shown in-game: capture the
        board region, template-match champion tiles, return the unit names.
        403 while toggled off; 503 until `.[scout]` extras + icons are installed."""
        if not scout_enabled:
            raise HTTPException(
                status_code=403,
                detail="screen scout is disabled — enable via POST /scout/toggle",
            )
        if not scout_available():
            raise HTTPException(
                status_code=503,
                detail=(
                    "scout extras missing — run: pip install -e '.[scout]' "
                    "&& python -m service.scripts.fetch_champ_icons"
                ),
            )
        return scout_board()

    @app.post("/advice", response_model=AdviceResponse)
    def advice(req: AdviceRequest) -> AdviceResponse:
        state = req.state
        comps = _library()
        engine = _engine()

        questions = build_questions(state, comps)
        fused: dict[str, FusedAnswer] = engine.decide(state.describe(), questions)

        by_slug = {c.slug: c for c in comps}
        opponent_units = [[u.name for u in o.units] for o in state.opponents]
        owned = _unit_names(state.board) | _unit_names(state.bench)
        merged_costs = {u: c for comp in comps for u, c in comp.unit_costs.items()}
        pool = pool_from_state(state, merged_costs)
        comp_advice: list[CompAdvice] = []
        if "comp" in fused:
            for slug, prob in sorted(
                fused["comp"].distribution.items(), key=lambda kv: kv[1], reverse=True
            ):
                if slug == FLEX_SLUG:
                    continue
                if len(comp_advice) >= req.top_n:
                    break
                comp = by_slug.get(slug)
                if comp:
                    entry = entry_signals(state, comp)
                    pairs = comp.key_unit_costs()
                    costs = [c for _, c in pairs]
                    key_units = [n for n, _ in pairs]
                    comp_advice.append(
                        CompAdvice(
                            slug=slug,
                            name=comp.name,
                            probability=round(prob, 3),
                            agreement=fused["comp"].agreement,
                            contested=contested_count(comp.units, opponent_units),
                            entry=entry.model_dump(),
                            pivot_to=pivot_candidates(state, comp, comps),
                            stats={
                                k: v
                                for k, v in {
                                    "avg_place": comp.avg_place,
                                    "top4": comp.top4,
                                    "pick_rate": comp.pick_rate,
                                }.items()
                                if v is not None
                            },
                            roll=(
                                roll_window(state.level, costs, pool, key_units)
                                if costs
                                else {}
                            ),
                            positioning=(
                                comp.positioning.model_dump()
                                if (
                                    comp.positioning.frontline
                                    or comp.positioning.backline
                                    or comp.positioning.notes
                                )
                                else {}
                            ),
                            missing_units=[
                                {
                                    "unit": u,
                                    "sub": comp.substitutes.get(u, []),
                                }
                                for u in comp.units
                                if u.lower() not in owned
                            ],
                            endgame=comp.endgame,
                            units=comp.units,
                            carry_items=comp.carry_items,
                            tank_items=comp.tank_items,
                            item_priority=comp.item_priority,
                            item_holders=comp.item_holders,
                            item_plan=comp.item_plan,
                        )
                    )
                if len(comp_advice) >= req.top_n:
                    break

        econ = None
        if "econ" in fused:
            econ = {
                "action": fused["econ"].choice,
                "distribution": fused["econ"].distribution,
                "agreement": fused["econ"].agreement,
            }

        augment = None
        if "augment" in fused:
            augment = {
                "pick": fused["augment"].choice,
                "distribution": fused["augment"].distribution,
                "agreement": fused["augment"].agreement,
            }

        pivot = fused["pivot"].noul if "pivot" in fused else None
        prep = fused["prep"].noul if "prep" in fused else None
        slam = fused["slam"].noul if "slam" in fused else None
        post_fight = fused["post_fight"].noul if "post_fight" in fused else None

        top_comp = comp_advice[0] if comp_advice else None
        top = by_slug.get(top_comp.slug) if top_comp else None
        shop = _shop_marks(state, top)
        carousel = _carousel_pick(state, top)
        next_ops = [
            NextOpponent(
                name=o.name or "?",
                shared=(
                    len({u.name.lower() for u in o.units} & {u.lower() for u in top.units})
                    if top
                    else 0
                ),
                units_known=len(o.units),
            )
            for o in state.next_opponent_candidates()
        ]

        engines = (
            [e.name for e in engine.engines]
            if hasattr(engine, "engines")
            else [engine.name]
        )
        return AdviceResponse(
            comps=comp_advice,
            econ=econ,
            augment=augment,
            pivot=pivot,
            prep=prep,
            slam=slam,
            post_fight=post_fight,
            carousel=carousel,
            shop=shop,
            next_opponents=next_ops,
            rival_names=[o.name for o in state.opponents if o.name],
            last_fought=state.fought_opponents[-1] if state.fought_opponents else "",
            engines=engines,
            stage=state.stage,
            level=state.level,
        )

    @app.get("/comps")
    def list_comps() -> dict:
        return {"comps": [c.model_dump() for c in _library()]}

    @app.post("/comps", status_code=201)
    def create_comp(body: CompIn) -> dict:
        if not body.name.strip():
            raise HTTPException(422, "name is required")
        comp = Comp(
            slug=slugify(body.name),
            name=body.name.strip(),
            units=body.units,
            traits=body.traits,
            carry_items=body.carry_items,
            conditions=body.conditions,
            strategy=body.strategy,
            positioning=body.positioning,
            unit_costs=body.unit_costs,
            sources=[SourceRating(site="custom")],
        )
        custom = [c for c in _read_custom() if c.slug != comp.slug]
        custom.append(comp)
        _write_custom(custom)
        return comp.model_dump()

    @app.delete("/comps/{slug}")
    def delete_comp(slug: str) -> dict:
        custom = _read_custom()
        remaining = [c for c in custom if c.slug != slug]
        if len(remaining) == len(custom):
            raise HTTPException(404, "no custom comp with that slug")
        _write_custom(remaining)
        return {"deleted": slug}

    return app


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="TFT Comp Advisor decision service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8371)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port)


app = create_app()

if __name__ == "__main__":
    main()
