from __future__ import annotations

import argparse
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .comps import (
    Comp,
    PivotOption,
    contested_count,
    entry_signals,
    load_library,
    pivot_candidates,
)
from .engines import Engine, FusedAnswer, build_default_engine
from .odds import roll_window
from .questions import FLEX_SLUG, build_questions
from .state import GameState

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_LIBRARY = DATA_DIR / "comps.json"


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


class AdviceResponse(BaseModel):
    comps: list[CompAdvice]
    econ: dict | None = None
    augment: dict | None = None
    pivot: float | None = None
    engines: list[str]
    stage: str
    level: int = 0


@lru_cache
def _engine() -> Engine:
    return build_default_engine()


@lru_cache
def _library() -> list[Comp]:
    path = Path(os.environ.get("TFT_COMPS", DEFAULT_LIBRARY))
    return load_library(path)


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

    @app.post("/advice", response_model=AdviceResponse)
    def advice(req: AdviceRequest) -> AdviceResponse:
        state = req.state
        comps = _library()
        engine = _engine()

        questions = build_questions(state, comps)
        fused: dict[str, FusedAnswer] = engine.decide(state.describe(), questions)

        by_slug = {c.slug: c for c in comps}
        opponent_units = [[u.name for u in o.units] for o in state.opponents]
        comp_advice: list[CompAdvice] = []
        if "comp" in fused:
            for slug, prob in sorted(
                fused["comp"].distribution.items(), key=lambda kv: kv[1], reverse=True
            ):
                if slug == FLEX_SLUG:
                    continue
                comp = by_slug.get(slug)
                if comp:
                    entry = entry_signals(state, comp)
                    costs = comp.carry_costs()
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
                            roll=roll_window(state.level, costs) if costs else {},
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
            engines=engines,
            stage=state.stage,
            level=state.level,
        )

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
