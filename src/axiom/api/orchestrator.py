import json
import time
import uuid
import logging
from datetime import datetime
from axiom.ai.groq import GroqProvider
from axiom.tools.registry import registry
from axiom.skills.registry import skill_registry
from axiom.observability.prism import prism
from sqlalchemy import select
from axiom.db.models.domain import AgentRun, Incident, IncidentStatus
from axiom.db.engine import async_session

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.ai = GroqProvider()

    async def process_report(self, text: str, image_url: str | None = None, latitude: float = 0, longitude: float = 0) -> dict:
        run_id = str(uuid.uuid4())
        session_id = f"run-{run_id[:8]}"
        start = time.time()
        tool_calls_log = []

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

        existing_incidents = await self._find_similar_incidents(category, latitude, longitude)
        incident_id = None
        is_new_incident = True
        if existing_incidents:
            incident_id = existing_incidents[0]["id"]
            is_new_incident = False
            tool_calls_log.append({"tool": "search_incidents", "result": f"Found {len(existing_incidents)} similar incidents, correlating with {incident_id}"})
            await self._add_report_to_incident(incident_id, text, latitude, longitude)
            if len(existing_incidents) > 1:
                ids = [i["id"] for i in existing_incidents[:3]]
                await registry.execute("correlate_incidents", incident_ids=ids)
        else:
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
            tool_calls_log.append({"tool": "create_incident", "result": f"Created incident {incident_id}"})

        dispatch_result = await registry.execute(
            "get_available_teams",
            category=category,
            latitude=latitude,
            longitude=longitude,
        )
        tool_calls_log.append({"tool": "get_available_teams", "result": f"Found {dispatch_result.data.get('count', 0)} teams" if dispatch_result.success else dispatch_result.error})

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
                tool_calls_log.append({"tool": "assign_team", "result": team_decision})
            else:
                tool_calls_log.append({"tool": "assign_team", "result": f"Failed: {assignment_result.error}"})
                alt_teams = [t for t in dispatch_result.data.get("teams", []) if t["id"] != team["id"]]
                for alt in alt_teams:
                    alt_result = await registry.execute("assign_team", team_id=alt["id"], incident_id=incident_id)
                    if alt_result.success:
                        team_decision = f"Replanned: Assigned {alt['name']} (ETA: {alt_result.data.get('eta_minutes', '?')} min)"
                        tool_calls_log.append({"tool": "assign_team", "result": team_decision})
                        break
        else:
            team_decision = "No available teams with matching capability"
            tool_calls_log.append({"tool": "dispatch", "result": team_decision})

        policy_result = await registry.execute("retrieve_policy", category=category)
        tool_calls_log.append({"tool": "retrieve_policy", "result": f"Found {policy_result.data.get('count', 0)} policies" if policy_result.success else "Failed"})

        response_text = await self._generate_response(
            text, analysis, team_decision, policy_result, is_new_incident, existing_incidents
        )

        latency = int((time.time() - start) * 1000)

        async with async_session() as db:
            run = (await db.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one()
            run.status = "completed"
            run.skill_used = skill_name
            run.completed_at = datetime.utcnow()
            run.outcome = response_text
            run.metadata_json = {
                "analysis": analysis,
                "team_decision": team_decision,
                "tool_calls": tool_calls_log,
                "is_new_incident": is_new_incident,
                "correlated_with": [i["id"] for i in existing_incidents] if existing_incidents else [],
            }
            await db.commit()

        await prism.trace_run(
            session_id=session_id,
            incident_id=incident_id,
            model=self.ai.strong_model,
            input_text=text,
            output_text=response_text,
            latency_ms=latency,
            metadata={
                "skill": skill_name,
                "category": category,
                "severity": severity,
                "confidence": confidence,
                "is_new_incident": is_new_incident,
                "tool_calls_count": len(tool_calls_log),
            },
        )

        return {
            "run_id": run_id,
            "incident_id": incident_id,
            "response": response_text,
            "analysis": analysis,
            "skill": skill_name,
            "team_decision": team_decision,
            "latency_ms": latency,
            "is_new_incident": is_new_incident,
            "correlated_with": [i["id"] for i in existing_incidents] if existing_incidents else [],
            "tool_calls": tool_calls_log,
        }

    async def replan_for_incident(self, incident_id: str) -> dict:
        start = time.time()
        tool_calls_log = []

        async with async_session() as db:
            incident = (await db.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()
            if not incident:
                return {"error": "Incident not found"}

        category = incident.category
        latitude = incident.latitude
        longitude = incident.longitude

        dispatch_result = await registry.execute(
            "get_available_teams",
            category=category,
            latitude=latitude,
            longitude=longitude,
            include_assigned=True,
        )
        tool_calls_log.append({"tool": "get_available_teams", "result": f"Found {dispatch_result.data.get('count', 0)} teams" if dispatch_result.success else "Failed"})

        team_decision = ""
        if dispatch_result.success and dispatch_result.data.get("teams"):
            for team in dispatch_result.data["teams"]:
                if team["status"] == "unavailable":
                    continue
                result = await registry.execute("assign_team", team_id=team["id"], incident_id=incident_id)
                if result.success:
                    team_decision = f"Replanned: Assigned {team['name']} (ETA: {result.data.get('eta_minutes', '?')} min)"
                    tool_calls_log.append({"tool": "assign_team", "result": team_decision})
                    break
                else:
                    tool_calls_log.append({"tool": "assign_team", "result": f"Failed for {team['name']}: {result.error}"})
        
        if not team_decision:
            team_decision = "No available teams - escalation required"

        response_text = await self.ai.generate(
            messages=[
                {"role": "system", "content": "You are AXIOM. Explain the replanning decision concisely. What changed, why the old plan failed, and what the new plan is."},
                {"role": "user", "content": f"Incident {incident_id} ({category}) needs replanning. Previous team unavailable. New decision: {team_decision}"},
            ],
            model=self.ai.fast_model,
        )

        latency = int((time.time() - start) * 1000)

        await prism.trace_run(
            session_id=f"replan-{incident_id[:8]}",
            incident_id=incident_id,
            model=self.ai.strong_model,
            input_text=f"Replan for incident {incident_id}",
            output_text=response_text.content,
            latency_ms=latency,
            metadata={"action": "replan", "tool_calls": tool_calls_log},
        )

        return {
            "incident_id": incident_id,
            "response": response_text.content,
            "team_decision": team_decision,
            "latency_ms": latency,
            "tool_calls": tool_calls_log,
        }

    async def _find_similar_incidents(self, category: str, latitude: float, longitude: float) -> list[dict]:
        result = await registry.execute(
            "search_incidents",
            category=category,
            latitude=latitude,
            longitude=longitude,
            radius_km=2.0,
        )
        if result.success and result.data.get("incidents"):
            return [
                i for i in result.data["incidents"]
                if i["status"] not in [IncidentStatus.RESOLVED.value, IncidentStatus.FAILED.value]
            ]
        return []

    async def _add_report_to_incident(self, incident_id: str, text: str, latitude: float, longitude: float):
        from axiom.db.models.domain import Report
        async with async_session() as db:
            report = Report(
                incident_id=incident_id,
                text=text,
                latitude=latitude,
                longitude=longitude,
                source_type="citizen",
            )
            db.add(report)
            await db.commit()

    async def _understand(self, text: str, image_url: str | None = None) -> dict:
        if image_url:
            response = await self.ai.analyze_image(
                image_url=image_url,
                prompt='''Analyze this city incident image. Return JSON:
{"category": "waste|water|accessibility|road", "severity": 1-5, "confidence": 0-1, "description": "brief description"}''',
            )
        else:
            response = await self.ai.generate(
                messages=[
                    {"role": "system", "content": '''You are AXIOM city incident classifier. Analyze the report and return JSON:
{"category": "waste|water|accessibility|road", "severity": 1-5, "confidence": 0-1, "description": "brief description"}
Categories:
- waste: garbage, bins, collection, trash, overflow, accumulation
- water: leaks, pipes, flooding, burst, water damage, puddles
- accessibility: ramps, pathways, ADA, blocked, wheelchair, disabled access
- road: hazards, obstructions, signs, potholes, traffic, fallen trees'''},
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

    async def _generate_response(
        self, original_text: str, analysis: dict, team_decision: str,
        policy_result: dict, is_new_incident: bool, existing_incidents: list[dict]
    ) -> str:
        policy_text = ""
        if policy_result.success and policy_result.data.get("policies"):
            policy_text = "\nRelevant policy:\n" + "\n".join(
                f"- {p['title']}: {p['content'][:150]}..."
                for p in policy_result.data["policies"][:1]
            )

        correlation_text = ""
        if existing_incidents:
            correlation_text = f"\nCorrelated with {len(existing_incidents)} existing incident(s) in the area. This is a follow-up report, not a new incident."

        system_prompt = (
            "You are AXIOM, an AI city operations supervisor. Respond concisely to operators.\n\n"
            "Analysis:\n"
            f"- Category: {analysis.get('category')}\n"
            f"- Severity: {analysis.get('severity')}/5\n"
            f"- Confidence: {analysis.get('confidence')}\n"
            f"- {'New incident created' if is_new_incident else 'Merged with existing incident'}\n"
            f"{team_decision}\n"
            f"{correlation_text}\n"
            f"{policy_text}\n\n"
            "Respond in 2-3 sentences. State the classification, what action was taken, and any relevant policy reference."
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
