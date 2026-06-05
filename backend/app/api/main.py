"""FastAPI app — API + live trace WebSocket.

Spec: docs/trace-view.md §3. Build-plan tasks 5.1-5.2. This is a runnable skeleton: the routes
exist with the correct shapes; fill in run_plan wiring (Phase 4) to make them do work.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.trace import create_emitter, get_emitter
from app.schemas import TraceEventType, UserProfile

settings = get_settings()
app = FastAPI(title="Health Plan Optimizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/plan")
async def start_plan(profile: UserProfile) -> dict:
    """Create a run, kick off the graph in the background, return the run_id immediately.

    TODO(5.2): replace the placeholder task with the real runner:
        from app.orchestration.runner import run_plan
        asyncio.create_task(run_plan(profile, run_id, emitter))
    """
    run_id = uuid.uuid4().hex[:8]
    emitter = create_emitter(run_id)
    await emitter.emit(TraceEventType.RUN_STARTED, summary="Run created", payload={})
    # asyncio.create_task(run_plan(profile, run_id, emitter))  # ← enable after Phase 4
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
            if event.type == TraceEventType.RUN_COMPLETED:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
