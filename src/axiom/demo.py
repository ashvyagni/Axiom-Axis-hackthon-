import time
import logging
from axiom.db.engine import async_session
from axiom.world.seed import seed_city
from axiom.api.orchestrator import orchestrator
from axiom.tools.registry import registry

logger = logging.getLogger(__name__)


class DemoScenario:
    """A scripted demo scenario for showcasing AXIOM capabilities."""
    
    def __init__(self, name: str, description: str, steps: list[dict]):
        self.name = name
        self.description = description
        self.steps = steps
        self.current_step = 0
        self.results = []
    
    async def reset(self):
        """Reset the database to a clean state."""
        from axiom.db.engine import engine, Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        async with async_session() as db:
            await seed_city(db)
        self.current_step = 0
        self.results = []
    
    async def run_next_step(self) -> dict:
        """Run the next step in the demo."""
        if self.current_step >= len(self.steps):
            return {"status": "complete", "message": "Demo complete"}
        
        step = self.steps[self.current_step]
        self.current_step += 1
        
        result = {"step": self.current_step, "action": step["action"]}
        
        try:
            if step["action"] == "report":
                r = await orchestrator.process_report(
                    text=step["text"],
                    latitude=step.get("lat", 40.7128),
                    longitude=step.get("lon", -74.006),
                )
                result["result"] = r
                result["incident_id"] = r.get("incident_id")
                
            elif step["action"] == "simulate":
                r = await registry.execute(
                    "simulate_event",
                    event_type=step["event_type"],
                    parameters=step.get("parameters", {}),
                )
                result["result"] = r.data if r.success else {"error": r.error}
                
            elif step["action"] == "replan":
                r = await orchestrator.replan_for_incident(step["incident_id"])
                result["result"] = r
            
            result["status"] = "success"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        self.results.append(result)
        return result


# Predefined demo scenarios
SCENARIOS = {
    "water_leak": DemoScenario(
        name="Water Leak Response",
        description="Citizen reports water leak → AXIOM classifies and dispatches → Team becomes unavailable → AXIOM replans",
        steps=[
            {
                "action": "report",
                "text": "Water leak at Main and 3rd intersection, water gushing from pipe!",
                "lat": 40.7128,
                "lon": -74.006,
            },
            {
                "action": "simulate",
                "event_type": "team_unavailable",
                "parameters": {"team_category": "water"},
            },
            {
                "action": "replan",
                "incident_id": "dynamic",  # Will be replaced with actual incident ID
            },
        ],
    ),
    "waste_overflow": DemoScenario(
        name="Waste Management",
        description="Multiple citizen reports about overflowing bins → AXIOM correlates → Dispatches waste team",
        steps=[
            {
                "action": "report",
                "text": "Garbage bins overflowing near Riverside market, trash everywhere!",
                "lat": 40.7160,
                "lon": -74.0018,
            },
            {
                "action": "report",
                "text": "Same issue - overflowing bins near Riverside market, getting worse.",
                "lat": 40.7159,
                "lon": -74.0022,
            },
        ],
    ),
    "accessibility": DemoScenario(
        name="Accessibility Incident",
        description="Blocked wheelchair ramp → AXIOM classifies as accessibility → Dispatches appropriate team",
        steps=[
            {
                "action": "report",
                "text": "Wheelchair ramp at City Hall is blocked by construction debris, disabled access impossible!",
                "lat": 40.7128,
                "lon": -74.006,
            },
        ],
    ),
    "road_hazard": DemoScenario(
        name="Road Hazard",
        description="Fallen tree blocking road → AXIOM classifies → Dispatches road incident team",
        steps=[
            {
                "action": "report",
                "text": "Fallen tree blocking the main road in Downtown Core, traffic stopped!",
                "lat": 40.7128,
                "lon": -74.006,
            },
        ],
    ),
    "vague_report": DemoScenario(
        name="Vague Report Handling",
        description="Vague citizen report → AXIOM detects uncertainty → Holds dispatch pending verification",
        steps=[
            {
                "action": "report",
                "text": "Something is wrong on Main Street.",
                "lat": 40.7128,
                "lon": -74.006,
            },
        ],
    ),
    "multi_incident": DemoScenario(
        name="Multiple Incidents",
        description="Multiple different incidents → AXIOM handles each independently → Shows resource management",
        steps=[
            {
                "action": "report",
                "text": "Water leak at Main and 3rd intersection.",
                "lat": 40.7128,
                "lon": -74.006,
            },
            {
                "action": "report",
                "text": "Fallen tree blocking Highway 5, debris on road.",
                "lat": 40.7150,
                "lon": -74.004,
            },
            {
                "action": "report",
                "text": "Garbage bin overflow in District 1, needs immediate attention.",
                "lat": 40.7140,
                "lon": -74.005,
            },
        ],
    ),
}


async def run_full_demo(scenario_name: str = "water_leak") -> dict:
    """Run a complete demo scenario and return results."""
    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        return {"error": f"Unknown scenario: {scenario_name}"}
    
    await scenario.reset()
    
    results = []
    for i, step in enumerate(scenario.steps):
        if step["action"] == "replan" and step["incident_id"] == "dynamic":
            if results and results[-1].get("incident_id"):
                step["incident_id"] = results[-1]["incident_id"]
        
        result = await scenario.run_next_step()
        results.append(result)
        
        if i < len(scenario.steps) - 1:
            time.sleep(1)
    
    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "steps": len(scenario.steps),
        "results": results,
    }


def list_scenarios() -> list[dict]:
    """List all available demo scenarios."""
    return [
        {
            "id": name,
            "name": scenario.name,
            "description": scenario.description,
            "steps": len(scenario.steps),
        }
        for name, scenario in SCENARIOS.items()
    ]
