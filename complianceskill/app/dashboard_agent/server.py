"""
CCE Layout Advisor — FastAPI Server
=====================================
REST API for the layout advisor agent.
The React frontend (layout_advisor_agent.jsx) calls these endpoints.

Endpoints:
  POST /sessions              → Create new session
  POST /sessions/{id}/start   → Start with upstream context
  POST /sessions/{id}/respond → Send user message
  GET  /sessions/{id}/state   → Get current state
  GET  /sessions/{id}/spec    → Get final layout spec
  DELETE /sessions/{id}       → Delete session
  GET  /templates             → List all templates
  GET  /templates/{id}        → Get template detail
  POST /templates/score       → Score templates against decisions
"""

from __future__ import annotations
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .runner import SessionManager, AdvisorResponse
from .templates import TEMPLATES, CATEGORIES


# ═══════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════

class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None


class StartSessionRequest(BaseModel):
    upstream_context: dict = Field(default_factory=dict)


class RespondRequest(BaseModel):
    message: str


class ScoreRequest(BaseModel):
    decisions: dict


class AdvisorResponseModel(BaseModel):
    agent_message: str
    phase: str
    is_complete: bool = False
    needs_input: bool = True
    options: list[str] = []
    recommended: list[dict] = []
    selected_template: Optional[str] = None
    layout_spec: Optional[dict] = None
    decisions_so_far: dict = {}
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════

manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown."""
    yield


app = FastAPI(
    title="CCE Layout Advisor Agent",
    description="Conversational layout advisor for the Causal Compliance Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════
# SESSION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.post("/sessions", response_model=dict)
async def create_session(req: CreateSessionRequest):
    """Create a new layout advisor session."""
    session_id = manager.create_session(req.session_id)
    return {"session_id": session_id}


@app.post("/sessions/{session_id}/start", response_model=AdvisorResponseModel)
async def start_session(session_id: str, req: StartSessionRequest):
    """Start the conversation with upstream context."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    response = session.start(req.upstream_context)
    return AdvisorResponseModel(**response.to_dict())


@app.post("/sessions/{session_id}/respond", response_model=AdvisorResponseModel)
async def respond_to_session(session_id: str, req: RespondRequest):
    """Send a user message to an active session."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    response = session.respond(req.message)
    return AdvisorResponseModel(**response.to_dict())


@app.get("/sessions/{session_id}/state", response_model=dict)
async def get_session_state(session_id: str):
    """Get current session state."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    state = session.get_state()
    # Serialize for JSON response
    return {
        "phase": state.get("phase", "unknown"),
        "decisions": state.get("decisions", {}),
        "selected_template_id": state.get("selected_template_id", ""),
        "message_count": len(state.get("messages", [])),
        "is_complete": state.get("phase") == "complete",
    }


@app.get("/sessions/{session_id}/spec", response_model=dict)
async def get_session_spec(session_id: str):
    """Get the final layout spec if the conversation is complete."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    spec = session.get_spec()
    if not spec:
        raise HTTPException(400, "Layout spec not yet generated. Complete the conversation first.")

    return spec


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    deleted = manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(404, f"Session {session_id} not found")
    return {"deleted": True}


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {"sessions": manager.list_sessions()}


# ═══════════════════════════════════════════════════════════════════════
# TEMPLATE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.get("/templates")
async def list_templates(category: Optional[str] = None):
    """List all templates, optionally filtered by category."""
    results = []
    for tid, tpl in TEMPLATES.items():
        if category and tpl["category"] != category:
            continue
        results.append({
            "id": tid,
            "name": tpl["name"],
            "icon": tpl.get("icon", ""),
            "category": tpl["category"],
            "description": tpl["description"],
            "complexity": tpl["complexity"],
            "domains": tpl["domains"],
            "best_for": tpl["best_for"],
        })
    return {"templates": results, "count": len(results)}


@app.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get full template detail."""
    tpl = TEMPLATES.get(template_id)
    if not tpl:
        raise HTTPException(404, f"Template '{template_id}' not found")
    return tpl


@app.post("/templates/score")
async def score_templates(req: ScoreRequest):
    """Score templates against decisions."""
    from vector_store import score_templates_hybrid

    ranked = score_templates_hybrid(req.decisions)
    results = []
    for tid, score, reasons in ranked[:10]:
        tpl = TEMPLATES[tid]
        results.append({
            "template_id": tid,
            "name": tpl["name"],
            "score": score,
            "reasons": reasons,
        })
    return {"results": results}


@app.get("/categories")
async def list_categories():
    """List all template categories."""
    return {"categories": CATEGORIES}


# ═══════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "templates": len(TEMPLATES),
        "active_sessions": len(manager.list_sessions()),
    }
