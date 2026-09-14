import math
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from axiom.db.models.domain import (
    Incident, Report, Team, TeamCapability, Assignment, District,
    Infrastructure, Policy, IncidentEvidence, WorldStateChange,
    IncidentStatus, TeamStatus,
)
from axiom.tools.registry import registry
from datetime import datetime


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


from contextlib import asynccontextmanager

@asynccontextmanager
async def _get_db():
    from axiom.db.engine import async_session
    async with async_session() as session:
        yield session


async def get_city_state(district_id: str | None = None) -> dict:
    async with _get_db() as db:
        if district_id:
            districts = (await db.execute(select(District).where(District.id == district_id))).scalars().all()
        else:
            districts = (await db.execute(select(District))).scalars().all()

        result = []
        for d in districts:
            infra = (await db.execute(
                select(Infrastructure).where(Infrastructure.district_id == d.id)
            )).scalars().all()
            incidents = (await db.execute(
                select(func.count(Incident.id)).where(Incident.district_id == d.id, Incident.status != IncidentStatus.RESOLVED.value)
            )).scalar() or 0
            teams = (await db.execute(
                select(func.count(Team.id))
            )).scalar() or 0
            result.append({
                "district": {"id": d.id, "name": d.name, "lat": d.latitude, "lon": d.longitude},
                "infrastructure_count": len(infra),
                "active_incidents": incidents,
                "total_teams": teams,
            })
        return {"districts": result}


registry.register(
    name="get_city_state",
    description="Get current city operational state, optionally filtered by district",
    parameters={"district_id": {"type": "string", "description": "Optional district ID filter"}},
    handler=get_city_state,
)


async def get_incident(incident_id: str) -> dict:
    async with _get_db() as db:
        incident = (await db.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()
        if not incident:
            return {"error": "Incident not found"}
        reports = (await db.execute(select(Report).where(Report.incident_id == incident.id))).scalars().all()
        return {
            "id": incident.id,
            "category": incident.category,
            "severity": incident.severity,
            "confidence": incident.confidence,
            "description": incident.description,
            "status": incident.status,
            "location": {"lat": incident.latitude, "lon": incident.longitude},
            "district_id": incident.district_id,
            "created_at": incident.created_at.isoformat(),
            "report_count": len(reports),
        }


registry.register(
    name="get_incident",
    description="Get details of a specific incident",
    parameters={"incident_id": {"type": "string", "description": "Incident ID"}},
    handler=get_incident,
)


async def search_incidents(
    category: str | None = None,
    status: str | None = None,
    district_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = 5.0,
) -> dict:
    async with _get_db() as db:
        query = select(Incident)
        if category:
            query = query.where(Incident.category == category)
        if status:
            query = query.where(Incident.status == status)
        if district_id:
            query = query.where(Incident.district_id == district_id)

        incidents = (await db.execute(query)).scalars().all()

        if latitude is not None and longitude is not None:
            incidents = [
                i for i in incidents
                if haversine(latitude, longitude, i.latitude, i.longitude) <= radius_km
            ]

        return {
            "incidents": [
                {
                    "id": i.id, "category": i.category, "severity": i.severity,
                    "status": i.status, "confidence": i.confidence,
                    "location": {"lat": i.latitude, "lon": i.longitude},
                    "created_at": i.created_at.isoformat(),
                }
                for i in incidents
            ],
            "count": len(incidents),
        }


registry.register(
    name="search_incidents",
    description="Search incidents by category, status, district, or location",
    parameters={
        "category": {"type": "string", "description": "Filter by category"},
        "status": {"type": "string", "description": "Filter by status"},
        "district_id": {"type": "string", "description": "Filter by district"},
        "latitude": {"type": "number", "description": "Center latitude for radius search"},
        "longitude": {"type": "number", "description": "Center longitude for radius search"},
        "radius_km": {"type": "number", "description": "Search radius in km (default 5)"},
    },
    handler=search_incidents,
)


async def create_incident(
    category: str,
    severity: int,
    confidence: float,
    description: str,
    latitude: float,
    longitude: float,
    district_id: str | None = None,
) -> dict:
    async with _get_db() as db:
        incident = Incident(
            category=category,
            severity=severity,
            confidence=confidence,
            description=description,
            latitude=latitude,
            longitude=longitude,
            district_id=district_id,
            status=IncidentStatus.REPORTED.value,
        )
        db.add(incident)
        await db.commit()
        await db.refresh(incident)
        return {
            "id": incident.id,
            "category": incident.category,
            "severity": incident.severity,
            "status": incident.status,
            "message": "Incident created successfully",
        }


registry.register(
    name="create_incident",
    description="Create a new incident in the system",
    parameters={
        "category": {"type": "string", "description": "Incident category (waste, water, accessibility, road)"},
        "severity": {"type": "integer", "description": "Severity level 1-5"},
        "confidence": {"type": "number", "description": "Classification confidence 0-1"},
        "description": {"type": "string", "description": "Incident description"},
        "latitude": {"type": "number", "description": "Location latitude"},
        "longitude": {"type": "number", "description": "Location longitude"},
        "district_id": {"type": "string", "description": "Optional district ID"},
    },
    handler=create_incident,
)


async def correlate_incidents(incident_ids: list[str], relation_type: str = "related") -> dict:
    from axiom.db.models.domain import IncidentRelation
    async with _get_db() as db:
        created = []
        for i in range(len(incident_ids)):
            for j in range(i + 1, len(incident_ids)):
                existing = (await db.execute(
                    select(IncidentRelation).where(
                        IncidentRelation.incident_a_id == incident_ids[i],
                        IncidentRelation.incident_b_id == incident_ids[j],
                    )
                )).scalar_one_or_none()
                if not existing:
                    rel = IncidentRelation(
                        incident_a_id=incident_ids[i],
                        incident_b_id=incident_ids[j],
                        relation_type=relation_type,
                    )
                    db.add(rel)
                    created.append({"a": incident_ids[i], "b": incident_ids[j]})
        await db.commit()
        return {"correlated": created, "count": len(created)}


registry.register(
    name="correlate_incidents",
    description="Link related incidents together",
    parameters={
        "incident_ids": {"type": "array", "items": {"type": "string"}, "description": "List of incident IDs to correlate"},
        "relation_type": {"type": "string", "description": "Type of relation (default: related)"},
    },
    handler=correlate_incidents,
)


async def get_available_teams(category: str | None = None, latitude: float | None = None, longitude: float | None = None, include_assigned: bool = False) -> dict:
    async with _get_db() as db:
        if include_assigned:
            query = select(Team).where(Team.status.in_([TeamStatus.AVAILABLE.value, TeamStatus.ASSIGNED.value]))
        else:
            query = select(Team).where(Team.status == TeamStatus.AVAILABLE.value)
        teams = (await db.execute(query)).scalars().all()

        result = []
        for t in teams:
            caps = (await db.execute(
                select(TeamCapability).where(TeamCapability.team_id == t.id)
            )).scalars().all()
            cap_categories = [c.category for c in caps]

            if category and category not in cap_categories:
                continue

            dist = None
            if latitude is not None and longitude is not None:
                dist = haversine(latitude, longitude, t.latitude, t.longitude)

            result.append({
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "capabilities": cap_categories,
                "location": {"lat": t.latitude, "lon": t.longitude},
                "distance_km": round(dist, 2) if dist else None,
            })

        if latitude is not None and longitude is not None:
            result.sort(key=lambda x: x["distance_km"] or 9999)

        return {"teams": result, "count": len(result)}


registry.register(
    name="get_available_teams",
    description="Get teams available for dispatch, optionally filtered by capability and proximity",
    parameters={
        "category": {"type": "string", "description": "Filter by capability category"},
        "latitude": {"type": "number", "description": "Reference latitude for distance sorting"},
        "longitude": {"type": "number", "description": "Reference longitude for distance sorting"},
        "include_assigned": {"type": "boolean", "description": "Include assigned teams for replanning (default false)"},
    },
    handler=get_available_teams,
)


async def get_team_details(team_id: str) -> dict:
    async with _get_db() as db:
        team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
        if not team:
            return {"error": "Team not found"}
        caps = (await db.execute(
            select(TeamCapability).where(TeamCapability.team_id == team.id)
        )).scalars().all()
        return {
            "id": team.id,
            "name": team.name,
            "status": team.status,
            "capabilities": [{"category": c.category, "proficiency": c.proficiency} for c in caps],
            "location": {"lat": team.latitude, "lon": team.longitude},
            "current_assignment": team.current_assignment_id,
        }


registry.register(
    name="get_team_details",
    description="Get detailed information about a specific team",
    parameters={"team_id": {"type": "string", "description": "Team ID"}},
    handler=get_team_details,
)


async def assign_team(team_id: str, incident_id: str) -> dict:
    async with _get_db() as db:
        team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
        if not team:
            return {"error": "Team not found"}
        if team.status != TeamStatus.AVAILABLE.value:
            return {"error": f"Team is not available (status: {team.status})"}

        incident = (await db.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()
        if not incident:
            return {"error": "Incident not found"}

        dist = haversine(team.latitude, team.longitude, incident.latitude, incident.longitude)
        eta = max(1, int(dist * 2))

        team.status = TeamStatus.ASSIGNED.value
        team.current_assignment_id = incident_id
        incident.status = IncidentStatus.ASSIGNED.value

        assignment = Assignment(
            team_id=team_id,
            incident_id=incident_id,
            status="assigned",
            eta_minutes=eta,
        )
        db.add(assignment)

        db.add(WorldStateChange(
            entity_type="team", entity_id=team_id,
            field="status", old_value=TeamStatus.AVAILABLE.value,
            new_value=TeamStatus.ASSIGNED.value, cause="assign_team",
        ))
        db.add(WorldStateChange(
            entity_type="incident", entity_id=incident_id,
            field="status", old_value=IncidentStatus.REPORTED.value,
            new_value=IncidentStatus.ASSIGNED.value, cause="assign_team",
        ))

        await db.commit()
        return {
            "assignment_id": assignment.id,
            "team": team.name,
            "incident_id": incident_id,
            "eta_minutes": eta,
            "message": f"Team {team.name} assigned to incident",
        }


registry.register(
    name="assign_team",
    description="Assign a team to an incident",
    parameters={
        "team_id": {"type": "string", "description": "Team ID to assign"},
        "incident_id": {"type": "string", "description": "Incident ID to assign to"},
    },
    handler=assign_team,
)


async def update_incident_status(incident_id: str, new_status: str, reason: str = "") -> dict:
    async with _get_db() as db:
        incident = (await db.execute(select(Incident).where(Incident.id == incident_id))).scalar_one_or_none()
        if not incident:
            return {"error": "Incident not found"}

        old_status = incident.status
        incident.status = new_status
        if new_status == IncidentStatus.RESOLVED.value:
            incident.resolved_at = datetime.utcnow()
            incident.resolution_notes = reason

        db.add(WorldStateChange(
            entity_type="incident", entity_id=incident_id,
            field="status", old_value=old_status,
            new_value=new_status, cause="update_status",
        ))
        await db.commit()
        return {"incident_id": incident_id, "old_status": old_status, "new_status": new_status}


registry.register(
    name="update_incident_status",
    description="Update the status of an incident",
    parameters={
        "incident_id": {"type": "string", "description": "Incident ID"},
        "new_status": {"type": "string", "description": "New status (acknowledged, assigned, dispatched, in_progress, resolved, failed, escalated)"},
        "reason": {"type": "string", "description": "Reason for status change"},
    },
    handler=update_incident_status,
)


async def retrieve_policy(category: str, context: str = "") -> dict:
    async with _get_db() as db:
        query = select(Policy).where(Policy.category == category)
        policies = (await db.execute(query)).scalars().all()
        return {
            "policies": [
                {"id": p.id, "title": p.title, "category": p.category, "content": p.content, "priority": p.priority}
                for p in policies
            ],
            "count": len(policies),
        }


registry.register(
    name="retrieve_policy",
    description="Retrieve relevant policies for an incident category",
    parameters={
        "category": {"type": "string", "description": "Incident category to find policies for"},
        "context": {"type": "string", "description": "Additional context for policy search"},
    },
    handler=retrieve_policy,
)


async def verify_resolution(incident_id: str, expected_outcome: str, observed_outcome: str) -> dict:
    from axiom.db.models.domain import VerificationResult
    async with _get_db() as db:
        status = "supported" if observed_outcome.strip().lower() == expected_outcome.strip().lower() else "contradicted"
        if not observed_outcome.strip():
            status = "insufficient_evidence"

        vr = VerificationResult(
            incident_id=incident_id,
            expected_outcome=expected_outcome,
            observed_outcome=observed_outcome,
            status=status,
        )
        db.add(vr)
        await db.commit()
        return {"verification_id": vr.id, "status": status, "incident_id": incident_id}


registry.register(
    name="verify_resolution",
    description="Verify whether an incident was actually resolved",
    parameters={
        "incident_id": {"type": "string", "description": "Incident ID to verify"},
        "expected_outcome": {"type": "string", "description": "What was expected to happen"},
        "observed_outcome": {"type": "string", "description": "What actually happened"},
    },
    handler=verify_resolution,
)


async def simulate_event(event_type: str, parameters: dict) -> dict:
    async with _get_db() as db:
        if event_type == "team_unavailable":
            team_id = parameters.get("team_id")
            team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
            if team:
                old_status = team.status
                team.status = TeamStatus.UNAVAILABLE.value
                team.current_assignment_id = None
                db.add(WorldStateChange(
                    entity_type="team", entity_id=team_id,
                    field="status", old_value=old_status,
                    new_value=TeamStatus.UNAVAILABLE.value, cause="simulate_event",
                ))
                await db.commit()
                return {"event": "team_unavailable", "team_id": team_id, "message": f"Team made unavailable"}

        elif event_type == "infrastructure_failure":
            infra_id = parameters.get("infrastructure_id")
            infra = (await db.execute(select(Infrastructure).where(Infrastructure.id == infra_id))).scalar_one_or_none()
            if infra:
                old_status = infra.status
                infra.status = "failed"
                db.add(WorldStateChange(
                    entity_type="infrastructure", entity_id=infra_id,
                    field="status", old_value=old_status,
                    new_value="failed", cause="simulate_event",
                ))
                await db.commit()
                return {"event": "infrastructure_failure", "infrastructure_id": infra_id}

        return {"error": f"Unknown event type: {event_type}"}


registry.register(
    name="simulate_event",
    description="Simulate a world event (team unavailable, infrastructure failure, etc.)",
    parameters={
        "event_type": {"type": "string", "description": "Event type (team_unavailable, infrastructure_failure)"},
        "parameters": {"type": "object", "description": "Event-specific parameters"},
    },
    handler=simulate_event,
)
