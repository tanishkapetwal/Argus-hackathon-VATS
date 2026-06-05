"""FastAPI app — API + live trace WebSocket.

Spec: docs/trace-view.md §3. Build-plan tasks 5.1-5.2. POST /api/plan kicks off the LangGraph
runner as a background task; the WS streams the trace live and GET replays it.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.trace import create_emitter, get_emitter
from app.orchestration.runner import run_plan
from app.schemas import TraceEventType, UserProfile

logger = logging.getLogger("app.api")
settings = get_settings()
app = FastAPI(title="Health Plan Optimizer")

app.add_middleware(
    CORSMiddleware,
    # The configured origin, plus ANY localhost/127.0.0.1 port (Vite hops to :5174 if :5173 is
    # taken). Without this the browser silently blocks POST /api/plan and the UI looks "frozen".
    allow_origins=[settings.frontend_origin],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep a reference to background run tasks so they aren't garbage-collected mid-flight.
_TASKS: set[asyncio.Task] = set()


async def _run_and_log(profile: UserProfile, run_id: str, emitter) -> None:
    """Drive run_plan; on an unexpected failure, surface an ERROR trace event (never crash)."""
    try:
        await run_plan(profile, run_id, emitter)
    except Exception as exc:  # pragma: no cover - defensive: keep the WS informative
        logger.exception("run_plan failed for %s", run_id)
        await emitter.emit(
            TraceEventType.ERROR, summary=f"Run failed: {exc}", payload={"error": str(exc)},
        )


@app.post("/api/plan")
async def start_plan(profile: UserProfile) -> dict:
    """Create a run, kick off the graph in the background, return the run_id immediately.

    The runner emits RUN_STARTED first and RUN_COMPLETED (with the HealthPlan) last; the WS
    replays the per-run buffer so a client that connects after this returns sees every event.
    """
    run_id = uuid.uuid4().hex[:8]
    emitter = create_emitter(run_id)
    task = asyncio.create_task(_run_and_log(profile, run_id, emitter))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return {"run_id": run_id}


@app.get("/api/plan/{run_id}")
async def get_plan(run_id: str) -> dict:
    """Replay: full event log + final plan (for reconnecting clients / non-WS clients)."""
    emitter = get_emitter(run_id)
    if emitter is None:
        return {"error": "unknown run_id"}
    events = [e.model_dump(mode="json") for e in emitter.events]
    plan = next(
        (e.payload for e in emitter.events if e.type == TraceEventType.RUN_COMPLETED), None
    )
    return {"events": events, "plan": plan}


@app.websocket("/ws/trace/{run_id}")
async def trace_ws(ws: WebSocket, run_id: str) -> None:
    """Stream TraceEvents (buffer replay + live) until RUN_COMPLETED. docs/trace-view.md §3."""
    await ws.accept()
    emitter = get_emitter(run_id)
    if emitter is None:
        await ws.send_json({"error": "unknown run_id"})
        await ws.close()
        return
    queue = emitter.subscribe()
    try:
        while True:
            event = await queue.get()
            await ws.send_json(event.model_dump(mode="json"))
            if event.type in (TraceEventType.RUN_COMPLETED, TraceEventType.ERROR):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
