import json
import re
import time
import uuid
import logging
from datetime import datetime
from axiom.ai.groq import GroqProvider
from axiom.tools.registry import registry
from axiom.skills.registry import skill_registry
from axiom.observability.prism import prism
from axiom.world.weather import weather_provider
from sqlalchemy import select
from axiom.db.models.domain import AgentRun, Incident, IncidentStatus, Report
from axiom.db.engine import async_session

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self):
        self.ai = GroqProvider()

    async def _generate_plan(
        self, analysis: dict, existing_incidents: list[dict],
        existing_reports: list[dict], weather: dict
    ) -> dict:
        """Generate an operational plan before taking action."""
        priority = "low"
        if analysis.get("severity", 1) >= 4:
            priority = "critical"
        elif analysis.get("severity", 1) >= 3:
            priority = "high"
        elif analysis.get("severity", 1) >= 2:
            priority = "medium"
        
        risk_factors = []
        if weather.get("is_adverse"):
            risk_factors.extend(weather.get("risk_factors", []))
        if analysis.get("confidence", 0.5) < 0.5:
            risk_factors.append("low_confidence")
        if existing_incidents:
            risk_factors.append("existing_incidents_in_area")
        
        return {
            "steps": [
                f"Classify {analysis.get('category')} incident",
                "Search for similar incidents",
                "Retrieve applicable policies",
                "Dispatch available team",
                "Verify outcome",
            ],
            "priority": priority,
            "risk_factors": risk_factors,
            "expected_outcome": f"Incident classified as {analysis.get('category')} severity {analysis.get('severity')}, team dispatched",
        }

    async def _verify_outcome(
        self, incident_id: str, action_taken: str, expected_outcome: str
    ) -> dict:
        """Verify whether the intended outcome was achieved."""
        result = await registry.execute("get_incident", incident_id=incident_id)
        if not result.success:
            return {"verified": False, "reason": "Could not retrieve incident"}
        
        incident = result.data
        current_status = incident.get("status", "unknown")
        
        verification = {
            "incident_id": incident_id,
            "action_taken": action_taken,
            "current_status": current_status,
            "verified": current_status in ["acknowledged", "in_progress"],
            "verification_time": datetime.utcnow().isoformat(),
        }
        
        if current_status == "resolved":
            verification["verified"] = True
            verification["outcome"] = "Incident marked as resolved"
        elif current_status == "failed":
            verification["verified"] = False
            verification["outcome"] = "Incident resolution failed"
            verification["replan_needed"] = True
        else:
            verification["verified"] = True
            verification["outcome"] = f"Incident is {current_status}, awaiting resolution"
        
        return verification

    async def process_report(self, text: str, image_url: str | None = None, latitude: float = 0, longitude: float = 0) -> dict:
        run_id = str(uuid.uuid4())
        session_id = f"run-{run_id[:8]}"
        run_start = time.time()
        tool_calls_log = []
        spans = []

        async with async_session() as db:
            run = AgentRun(id=run_id, session_id=session_id, status="running")
            db.add(run)
            await db.commit()

        span_understand_start = time.time()
        existing_incidents = await self._find_similar_incidents(None, latitude, longitude)
        existing_reports = await self._get_existing_reports(existing_incidents)
        analysis = await self._understand(text, image_url, existing_reports, existing_incidents, latitude, longitude)
        prism.finish_span(
            spans[-1] if spans else prism.create_span("search_incidents", "tool", input_text=f"lat={latitude} lon={longitude}"),
            span_understand_start,
        ) if spans else None
        category = analysis.get("category", "waste")
        severity = analysis.get("severity", 1)
        confidence = analysis.get("confidence", 0.5)
        description = analysis.get("description", text)
        uncertainty_reason = analysis.get("uncertainty_reason", None)
        skill_name = self._select_skill(category)

        span_understand = prism.create_span(
            name="understand_report",
            span_type="llm",
            input_text=text[:500],
            output_text=json.dumps(analysis)[:500],
            model=self.ai.fast_model,
        )
        span_understand["start_time"] = prism._now_iso()
        span_understand["duration_ms"] = int((time.time() - span_understand_start) * 1000)
        spans.append(span_understand)

        span_plan_start = time.time()
        weather = await weather_provider.get_weather(latitude, longitude)
        plan = await self._generate_plan(analysis, existing_incidents, existing_reports, weather)
        span_plan = prism.create_span(
            name="generate_plan",
            span_type="llm",
            input_text=json.dumps({"category": category, "severity": severity})[:500],
            output_text=json.dumps(plan)[:500],
            model=self.ai.fast_model,
        )
        span_plan["duration_ms"] = int((time.time() - span_plan_start) * 1000)
        spans.append(span_plan)

        incident_id = None
        is_new_incident = True
        if existing_incidents:
            incident_id = existing_incidents[0]["id"]
            is_new_incident = False
            tool_calls_log.append({"tool": "search_incidents", "result": f"Found {len(existing_incidents)} similar incidents"})
            await self._add_report_to_incident(incident_id, text, latitude, longitude)
            span_search = prism.create_span(
                name="search_incidents",
                span_type="tool",
                input_text=f"category={category} lat={latitude} lon={longitude} radius=2km",
                output_text=f"Found {len(existing_incidents)} incidents",
                metadata={"incident_ids": [i["id"] for i in existing_incidents[:3]]},
            )
            spans.append(span_search)

            if existing_incidents[0].get("severity", 1) < severity:
                span_escalate_start = time.time()
                await registry.execute(
                    "update_incident_status",
                    incident_id=incident_id,
                    new_status="acknowledged",
                    reason=f"Severity escalated from {existing_incidents[0].get('severity', 1)} to {severity} based on new evidence",
                )
                tool_calls_log.append({"tool": "update_severity", "result": f"Escalated severity to {severity}"})
                span_escalate = prism.create_span(
                    name="escalate_severity",
                    span_type="tool",
                    input_text=f"incident={incident_id} from={existing_incidents[0].get('severity', 1)} to={severity}",
                    output_text="Escalated",
                )
                span_escalate["duration_ms"] = int((time.time() - span_escalate_start) * 1000)
                spans.append(span_escalate)

            if len(existing_incidents) > 1:
                ids = [i["id"] for i in existing_incidents[:3]]
                span_correlate_start = time.time()
                await registry.execute("correlate_incidents", incident_ids=ids)
                span_correlate = prism.create_span(
                    name="correlate_incidents",
                    span_type="tool",
                    input_text=f"incident_ids={ids}",
                    output_text=f"Correlated {len(ids)} incidents",
                )
                span_correlate["duration_ms"] = int((time.time() - span_correlate_start) * 1000)
                spans.append(span_correlate)
        else:
            span_create_start = time.time()
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
            span_create = prism.create_span(
                name="create_incident",
                span_type="tool",
                input_text=f"category={category} severity={severity} confidence={confidence}",
                output_text=f"Created {incident_id}",
                metadata={"incident_id": incident_id},
            )
            span_create["duration_ms"] = int((time.time() - span_create_start) * 1000)
            spans.append(span_create)

        team_decision = ""
        if confidence >= 0.4:
            span_dispatch_start = time.time()
            dispatch_result = await registry.execute(
                "get_available_teams",
                category=category,
                latitude=latitude,
                longitude=longitude,
            )
            tool_calls_log.append({"tool": "get_available_teams", "result": f"Found {dispatch_result.data.get('count', 0)} teams" if dispatch_result.success else dispatch_result.error})

            if dispatch_result.success and dispatch_result.data.get("teams"):
                team = dispatch_result.data["teams"][0]
                span_assign_start = time.time()
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
                span_assign = prism.create_span(
                    name="assign_team",
                    span_type="tool",
                    input_text=f"team={team['id']} incident={incident_id}",
                    output_text=team_decision,
                    metadata={"team_name": team["name"]},
                )
                span_assign["duration_ms"] = int((time.time() - span_assign_start) * 1000)
                spans.append(span_assign)
            else:
                team_decision = "No available teams with matching capability"
                tool_calls_log.append({"tool": "dispatch", "result": team_decision})
            span_dispatch = prism.create_span(
                name="dispatch_team",
                span_type="tool",
                input_text=f"category={category} lat={latitude} lon={longitude}",
                output_text=team_decision,
            )
            span_dispatch["duration_ms"] = int((time.time() - span_dispatch_start) * 1000)
            spans.append(span_dispatch)
        else:
            team_decision = "HOLD: Insufficient confidence for dispatch - additional verification recommended"
            tool_calls_log.append({"tool": "dispatch", "result": team_decision})

        span_policy_start = time.time()
        policy_result = await registry.execute("retrieve_policy", category=category)
        tool_calls_log.append({"tool": "retrieve_policy", "result": f"Found {policy_result.data.get('count', 0)} policies" if policy_result.success else "Failed"})
        span_policy = prism.create_span(
            name="retrieve_policy",
            span_type="tool",
            input_text=f"category={category}",
            output_text=f"Found {policy_result.data.get('count', 0)} policies" if policy_result.success else "Failed",
        )
        span_policy["duration_ms"] = int((time.time() - span_policy_start) * 1000)
        spans.append(span_policy)

        if incident_id and team_decision and "Assigned" in team_decision:
            span_verify_start = time.time()
            verification = await self._verify_outcome(
                incident_id,
                team_decision,
                plan.get("expected_outcome", "Incident addressed"),
            )
            span_verify = prism.create_span(
                name="verify_outcome",
                span_type="tool",
                input_text=f"incident={incident_id} action={team_decision}",
                output_text=json.dumps(verification)[:500],
            )
            span_verify["duration_ms"] = int((time.time() - span_verify_start) * 1000)
            spans.append(span_verify)
        else:
            verification = {"verified": False, "reason": "No action taken"}

        span_response_start = time.time()
        response_text = await self._generate_response(
            text, analysis, team_decision, policy_result, is_new_incident,
            existing_incidents, existing_reports, uncertainty_reason
        )
        span_response = prism.create_span(
            name="generate_response",
            span_type="llm",
            input_text=text[:500],
            output_text=response_text[:500],
            model=self.ai.fast_model,
        )
        span_response["duration_ms"] = int((time.time() - span_response_start) * 1000)
        spans.append(span_response)

        latency = int((time.time() - run_start) * 1000)

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
                "uncertainty_reason": uncertainty_reason,
                "evidence_count": len(existing_reports) + 1,
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
                "uncertainty_reason": uncertainty_reason,
                "evidence_count": len(existing_reports) + 1,
            },
            spans=spans,
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
            "uncertainty_reason": uncertainty_reason,
        }

    async def replan_for_incident(self, incident_id: str) -> dict:
        run_start = time.time()
        tool_calls_log = []
        spans = []

        async with async_session() as db:
            incident = (await db.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()
            if not incident:
                return {"error": "Incident not found"}

        category = incident.category
        latitude = incident.latitude
        longitude = incident.longitude

        span_dispatch_start = time.time()
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
                span_assign_start = time.time()
                result = await registry.execute("assign_team", team_id=team["id"], incident_id=incident_id)
                if result.success:
                    team_decision = f"Replanned: Assigned {team['name']} (ETA: {result.data.get('eta_minutes', '?')} min)"
                    tool_calls_log.append({"tool": "assign_team", "result": team_decision})
                    span_assign = prism.create_span(
                        name="replan_assign_team",
                        span_type="tool",
                        input_text=f"team={team['id']} incident={incident_id}",
                        output_text=team_decision,
                        metadata={"team_name": team["name"]},
                    )
                    span_assign["duration_ms"] = int((time.time() - span_assign_start) * 1000)
                    spans.append(span_assign)
                    break
                else:
                    tool_calls_log.append({"tool": "assign_team", "result": f"Failed for {team['name']}: {result.error}"})
        
        if not team_decision:
            team_decision = "No available teams - escalation required"

        span_dispatch = prism.create_span(
            name="replan_dispatch",
            span_type="tool",
            input_text=f"incident={incident_id} category={category}",
            output_text=team_decision,
        )
        span_dispatch["duration_ms"] = int((time.time() - span_dispatch_start) * 1000)
        spans.append(span_dispatch)

        span_llm_start = time.time()
        response_text = await self.ai.generate(
            messages=[
                {"role": "system", "content": (
                    "You are AXIOM. Explain replanning concisely:\n"
                    "1. What changed\n2. Why old plan failed\n3. New plan (team, ETA)\n4. What happens next\n"
                    "Be specific. Do not hallucinate."
                )},
                {"role": "user", "content": (
                    f"Incident {incident_id[:8]} ({category}) needs replanning.\n"
                    f"Previous team unavailable.\nNew: {team_decision}"
                )},
            ],
            model=self.ai.fast_model,
            max_tokens=200,
        )
        span_llm = prism.create_span(
            name="replan_generate_response",
            span_type="llm",
            input_text=f"Replan for {incident_id[:8]} ({category})",
            output_text=response_text.content[:500],
            model=self.ai.fast_model,
        )
        span_llm["duration_ms"] = int((time.time() - span_llm_start) * 1000)
        spans.append(span_llm)

        latency = int((time.time() - run_start) * 1000)

        await prism.trace_run(
            session_id=f"replan-{incident_id[:8]}",
            incident_id=incident_id,
            model=self.ai.strong_model,
            input_text=f"Replan for incident {incident_id}",
            output_text=response_text.content,
            latency_ms=latency,
            metadata={"action": "replan", "tool_calls": tool_calls_log},
            spans=spans,
        )

        return {
            "incident_id": incident_id,
            "response": response_text.content,
            "team_decision": team_decision,
            "latency_ms": latency,
            "tool_calls": tool_calls_log,
        }

    async def _find_similar_incidents(self, category: str | None, latitude: float, longitude: float) -> list[dict]:
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

    async def _get_existing_reports(self, incidents: list[dict]) -> list[dict]:
        if not incidents:
            return []
        reports = []
        for inc in incidents[:2]:
            result = await registry.execute("get_incident", incident_id=inc["id"])
            if result.success and result.data:
                reports.append(result.data)
        return reports

    async def _add_report_to_incident(self, incident_id: str, text: str, latitude: float, longitude: float):
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

    async def _understand(
        self, text: str, image_url: str | None,
        existing_reports: list[dict], existing_incidents: list[dict],
        latitude: float = 0, longitude: float = 0
    ) -> dict:
        context = ""
        if existing_reports:
            context = "\nEXISTING: "
            for r in existing_reports[:2]:
                context += f"Severity {r.get('severity', '?')}/5. "
            context += "Consider if new report confirms or contradicts."

        weather = await weather_provider.get_weather(latitude, longitude)
        weather_context = ""
        if weather.get("is_adverse"):
            weather_context = f"\nWEATHER ALERT: {weather['condition']}, {weather['temperature_c']}°C, wind {weather['wind_speed_kmh']}km/h. Risks: {', '.join(weather.get('risk_factors', []))}. If report mentions weather-related issues (flooding, wind damage, ice), increase severity."

        if image_url:
            response = await self.ai.analyze_image(
                image_url=image_url,
                prompt='''Analyze this city incident image. Return JSON:
{"category": "waste|water|accessibility|road", "severity": 1-5, "confidence": 0-1, "description": "brief description", "uncertainty_reason": "null or reason for low confidence"}''',
            )
        else:
            response = await self.ai.generate(
                messages=[
                    {"role": "system", "content": f'''AXIOM incident classifier. Return JSON:
{{"category": "waste|water|accessibility|road", "severity": 1-5, "confidence": 0-1, "description": "brief", "uncertainty_reason": "null or why low confidence"}}

Categories: waste (garbage,bins), water (leaks,pipes), accessibility (ramps,ADA), road (hazards,signs)

CONFIDENCE: <0.5 if vague, contradicts existing, or unclear. uncertainty_reason required if confidence<0.6.
SEVERITY: 1=cosmetic, 2=needs attention, 3=moderate, 4=significant, 5=emergency{context}{weather_context}'''},
                    {"role": "user", "content": text},
                ],
                model=self.ai.fast_model,
                response_format={"type": "json_object"},
                max_tokens=200,
            )

        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "category": "waste",
                "severity": 1,
                "confidence": 0.2,
                "description": text,
                "uncertainty_reason": "Failed to parse classification"
            }

        heuristic_conf, heuristic_reason = self._heuristic_uncertainty(text)
        if heuristic_conf < parsed.get("confidence", 0.5):
            parsed["confidence"] = heuristic_conf
            parsed["uncertainty_reason"] = heuristic_reason

        if parsed.get("confidence", 0.5) < 0.6 and not parsed.get("uncertainty_reason"):
            parsed["uncertainty_reason"] = "Low confidence due to limited or ambiguous information in report"

        return parsed

    def _heuristic_uncertainty(self, text: str) -> tuple[float, str | None]:
        vague_patterns = [
            (r"^.{0,30}$", "Report is very short with no specific details"),
            (r"\bsomething\b", "Report uses vague language ('something')"),
            (r"\b(weird|wrong|strange|off|not right)\b", "Report uses vague descriptors"),
            (r"\bmaybe|perhaps|possibly|might be\b", "Report expresses uncertainty"),
            (r"\bi think|i feel like|seems like\b", "Report is subjective"),
            (r"\b(somewhere|around here|over there)\b", "Report lacks specific location"),
        ]
        for pattern, reason in vague_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return 0.3, reason
        return 1.0, None

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
        policy_result: dict, is_new_incident: bool, existing_incidents: list[dict],
        existing_reports: list[dict], uncertainty_reason: str | None
    ) -> str:
        policy_text = ""
        if policy_result.success and policy_result.data.get("policies"):
            policy_text = "\nRelevant policy:\n" + "\n".join(
                f"- {p['title']}: {p['content'][:150]}..."
                for p in policy_result.data["policies"][:1]
            )

        correlation_text = ""
        if existing_incidents:
            correlation_text = f"\nCorrelated with {len(existing_incidents)} existing incident(s) in the area."

        uncertainty_text = ""
        if uncertainty_reason:
            uncertainty_text = f"\nNote: {uncertainty_reason}. Confidence is limited - additional verification may be needed."

        evidence_text = ""
        if existing_reports:
            evidence_text = f"\nExisting evidence in area: {len(existing_reports)} prior report(s)."

        system_prompt = (
            "You are AXIOM, an AI city operations supervisor. Respond concisely to operators.\n\n"
            "Analysis:\n"
            f"- Category: {analysis.get('category')}\n"
            f"- Severity: {analysis.get('severity')}/5\n"
            f"- Confidence: {analysis.get('confidence')}\n"
            f"- {'New incident created' if is_new_incident else 'Merged with existing incident'}\n"
            f"{team_decision}\n"
            f"{correlation_text}"
            f"{evidence_text}"
            f"{uncertainty_text}\n"
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
