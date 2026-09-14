import json
import time
import uuid
import logging
from axiom.ai.groq import GroqProvider
from axiom.tools.registry import registry
from axiom.skills.registry import skill_registry
from axiom.observability.prism import prism
from sqlalchemy import select
from axiom.db.models.domain import AgentRun, ToolCall, Incident, IncidentCategory
from axiom.db.engine import async_session

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.ai = GroqProvider()

    async def process_report(self, text: str, image_url: str | None = None, latitude: float = 0, longitude: float = 0) -> dict:
        run_id = str(uuid.uuid4())
        session_id = f"run-{run_id[:8]}"
        start = time.time()

        async with async_session() as db:
            run = AgentRun(id=run_id, session_id=session_id, status="running")
            db.add(run)
            await db.commit()

        analysis = await self._understand(text, image_url)
        category = analysis.get("category", "waste")
        severity = analysis.get("severity", 1)
        confidence = analysis.get("confidence", 0.5)
        description = analysis.get("description", text)

        skill_name = self._select_skill(category)
        skill = skill_registry.get(skill_name)

        available_tools = skill.allowed_tools if skill else registry.list_tools()

        incident_result = await registry.execute(
            "create_incident",
            category=category,
            severity=severity,
            confidence=confidence,
            description=description,
            latitude=latitude,
            longitude=longitude,
        )
        incident_id = incident_result.data.get("id") if incident_result.success else None

        dispatch_result = await registry.execute(
            "get_available_teams",
            category=category,
            latitude=latitude,
            longitude=longitude,
        )

        team_decision = ""
        assignment_result = None
        if dispatch_result.success and dispatch_result.data.get("teams"):
            team = dispatch_result.data["teams"][0]
            assignment_result = await registry.execute(
                "assign_team",
                team_id=team["id"],
                incident_id=incident_id,
            )
            if assignment_result.success:
                team_decision = f"Assigned {team['name']} (ETA: {assignment_result.data.get('eta_minutes', '?')} min)"

        policy_result = await registry.execute("retrieve_policy", category=category)

        plan_text = f"Category: {category}\nSeverity: {severity}\nConfidence: {confidence}\nSkill: {skill_name}\n{team_decision}"

        response_text = await self._generate_response(text, analysis, team_decision, policy_result)

        latency = int((time.time() - start) * 1000)

        async with async_session() as db:
            run = (await db.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one()
            run.status = "completed"
            run.skill_used = skill_name
            run.completed_at = __import__("datetime").datetime.utcnow()
            run.outcome = response_text
            run.metadata_json = {"analysis": analysis, "team_decision": team_decision}
            await db.commit()

        await prism.trace_run(
            session_id=session_id,
            incident_id=incident_id,
            model=self.ai.strong_model,
            input_text=text,
            output_text=response_text,
            latency_ms=latency,
            metadata={"skill": skill_name, "category": category, "severity": severity},
        )

        return {
            "run_id": run_id,
            "incident_id": incident_id,
            "response": response_text,
            "analysis": analysis,
            "skill": skill_name,
            "team_decision": team_decision,
            "latency_ms": latency,
        }

    async def _understand(self, text: str, image_url: str | None = None) -> dict:
        if image_url:
            response = await self.ai.analyze_image(
                image_url=image_url,
                prompt="""Analyze this city incident image. Return JSON:
{"category": "waste|water|accessibility|road", "severity": 1-5, "confidence": 0-1, "description": "brief description"}""",
            )
        else:
            response = await self.ai.generate(
                messages=[
                    {"role": "system", "content": """You are AXIOM city incident classifier. Analyze the report and return JSON:
{"category": "waste|water|accessibility|road", "severity": 1-5, "confidence": 0-1, "description": "brief description"}
Categories: waste (garbage, bins, collection), water (leaks, pipes, flooding), accessibility (ramps, pathways, ADA), road (hazards, obstructions, signs)."""},
                    {"role": "user", "content": text},
                ],
                model=self.ai.fast_model,
                response_format={"type": "json_object"},
            )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"category": "waste", "severity": 1, "confidence": 0.3, "description": text}

    def _select_skill(self, category: str) -> str:
        mapping = {
            "waste": "waste_management",
            "water": "water_infrastructure",
            "accessibility": "accessibility",
            "road": "road_incident",
        }
        return mapping.get(category, "waste_management")

    async def _generate_response(self, original_text: str, analysis: dict, team_decision: str, policy_result: dict) -> str:
        policy_text = ""
        if policy_result.success and policy_result.data.get("policies"):
            policy_text = "\nRelevant policies:\n" + "\n".join(
                f"- {p['title']}: {p['content'][:100]}..."
                for p in policy_result.data["policies"][:2]
            )

        system_prompt = (
            "You are AXIOM, an AI city operations supervisor. Respond concisely to operators.\n\n"
            f"Current analysis:\n"
            f"- Category: {analysis.get('category')}\n"
            f"- Severity: {analysis.get('severity')}/5\n"
            f"- Confidence: {analysis.get('confidence')}\n"
            f"{team_decision}\n"
            f"{policy_text}\n\n"
            "Respond in 2-3 sentences. State what was classified, what action was taken, and any relevant policy reference."
        )

        response = await self.ai.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Operator report: {original_text}"},
            ],
            model=self.ai.fast_model,
        )
        return response.content


orchestrator = Orchestrator()
