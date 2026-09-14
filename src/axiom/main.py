from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from axiom.db.engine import init_db, async_session
from axiom.tools.registry import registry
from axiom.skills.registry import skill_registry
from axiom.world.seed import seed_city
from axiom.world.weather import weather_provider
from axiom.api.orchestrator import orchestrator
from axiom.tools.implementations.core_tools import haversine
from pathlib import Path

app = FastAPI(title="AXIOM", description="AI-powered city operations supervisor", version="0.1.0")

frontend_dir = Path(__file__).parent.parent.parent / "frontend"


class ReportRequest(BaseModel):
    text: str
    image_url: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0


class EventRequest(BaseModel):
    event_type: str
    parameters: dict = {}


@app.on_event("startup")
async def startup():
    await init_db()
    async with async_session() as db:
        await seed_city(db)


@app.get("/")
async def root():
    return {"name": "AXIOM", "version": "0.1.0", "status": "operational"}


@app.get("/api/tools")
async def list_tools():
    return {"tools": registry.list_tools()}


@app.get("/api/skills")
async def list_skills():
    return {"skills": skill_registry.list_skills()}


@app.post("/api/report")
async def submit_report(req: ReportRequest):
    result = await orchestrator.process_report(
        text=req.text,
        image_url=req.image_url,
        latitude=req.latitude,
        longitude=req.longitude,
    )
    return result


@app.get("/api/incidents")
async def list_incidents(category: str | None = None, status: str | None = None):
    result = await registry.execute("search_incidents", category=category, status=status)
    return result.data


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    result = await registry.execute("get_incident", incident_id=incident_id)
    return result.data


@app.get("/api/teams")
async def list_teams(category: str | None = None):
    result = await registry.execute("get_available_teams", category=category)
    return result.data


@app.get("/api/city-state")
async def city_state(district_id: str | None = None):
    result = await registry.execute("get_city_state", district_id=district_id)
    return result.data


@app.post("/api/simulate")
async def simulate(req: EventRequest):
    result = await registry.execute("simulate_event", event_type=req.event_type, parameters=req.parameters)
    return result.data


@app.get("/api/weather")
async def get_weather(latitude: float = 40.7128, longitude: float = -74.006):
    return await weather_provider.get_weather(latitude, longitude)


@app.post("/api/replan/{incident_id}")
async def replan(incident_id: str):
    result = await orchestrator.replan_for_incident(incident_id)
    return result


@app.get("/api/runs")
async def list_runs():
    from axiom.db.models.domain import AgentRun
    from sqlalchemy import select
    async with async_session() as db:
        runs = (await db.execute(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(20))).scalars().all()
        return {"runs": [
            {"id": r.id, "session_id": r.session_id, "status": r.status,
             "skill_used": r.skill_used, "outcome": r.outcome,
             "started_at": r.started_at.isoformat() if r.started_at else None}
            for r in runs
        ]}


@app.get("/dashboard")
async def dashboard():
    return FileResponse(frontend_dir / "index.html")


if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
