import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from axiom.db.models.domain import (
    District, Infrastructure, Team, TeamCapability, Policy, IncidentCategory
)


async def seed_city(db: AsyncSession):
    existing = (await db.execute(select(District))).scalars().first()
    if existing:
        return {"status": "already_seeded"}

    districts = [
        District(id=str(uuid.uuid4()), name="Downtown Core", latitude=40.7128, longitude=-74.0060, population=50000, priority=1),
        District(id=str(uuid.uuid4()), name="Riverside", latitude=40.7158, longitude=-74.0020, population=35000, priority=2),
        District(id=str(uuid.uuid4()), name="Hillcrest", latitude=40.7098, longitude=-74.0100, population=25000, priority=3),
        District(id=str(uuid.uuid4()), name="Industrial Zone", latitude=40.7080, longitude=-74.0150, population=10000, priority=2),
    ]
    db.add_all(districts)
    await db.flush()

    infra_items = []
    for d in districts:
        infra_items.extend([
            Infrastructure(id=str(uuid.uuid4()), name=f"Water Main - {d.name}", type="water",
                          district_id=d.id, latitude=d.latitude + 0.002, longitude=d.longitude + 0.001, status="operational"),
            Infrastructure(id=str(uuid.uuid4()), name=f"Street Lights - {d.name}", type="electricity",
                          district_id=d.id, latitude=d.latitude - 0.001, longitude=d.longitude + 0.002, status="operational"),
            Infrastructure(id=str(uuid.uuid4()), name=f"Bin Station - {d.name}", type="waste",
                          district_id=d.id, latitude=d.latitude + 0.001, longitude=d.longitude - 0.001, status="operational"),
            Infrastructure(id=str(uuid.uuid4()), name=f"Road Network - {d.name}", type="road",
                          district_id=d.id, latitude=d.latitude, longitude=d.longitude, status="operational"),
            Infrastructure(id=str(uuid.uuid4()), name=f"Accessibility Ramps - {d.name}", type="accessibility",
                          district_id=d.id, latitude=d.latitude + 0.0005, longitude=d.longitude + 0.0005, status="operational"),
        ])
    db.add_all(infra_items)

    teams = [
        Team(id=str(uuid.uuid4()), name="Alpha Response", status="available",
             latitude=40.7130, longitude=-74.0055),
        Team(id=str(uuid.uuid4()), name="Bravo Services", status="available",
             latitude=40.7155, longitude=-74.0025),
        Team(id=str(uuid.uuid4()), name="Charlie Maintenance", status="available",
             latitude=40.7100, longitude=-74.0095),
        Team(id=str(uuid.uuid4()), name="Delta Emergency", status="available",
             latitude=40.7085, longitude=-74.0145),
    ]
    db.add_all(teams)
    await db.flush()

    cap_map = {
        0: ["waste", "road"],
        1: ["water", "accessibility"],
        2: ["waste", "water", "road"],
        3: ["road", "accessibility", "water"],
    }
    for idx, team in enumerate(teams):
        for cat in cap_map[idx]:
            db.add(TeamCapability(id=str(uuid.uuid4()), team_id=team.id, category=cat, proficiency=3))

    policies = [
        Policy(id=str(uuid.uuid4()), title="Waste Collection Response Protocol", category="waste",
               content="Waste overflow incidents must be addressed within 4 hours of report. Priority increases for areas near schools, hospitals, or food establishments. Escalate if bin capacity exceeded by more than 200%.",
               relevant_categories=["waste"], priority=1),
        Policy(id=str(uuid.uuid4()), title="Water Emergency Response", category="water",
               content="Water leaks classified as critical if affecting more than 10 households or near electrical infrastructure. Emergency shutoff team must be dispatched within 30 minutes for critical leaks.",
               relevant_categories=["water"], priority=1),
        Policy(id=str(uuid.uuid4()), title="Accessibility Compliance", category="accessibility",
               content="Accessibility obstruction reports are high priority. All public pathway obstructions must be cleared within 2 hours. ADA compliance requires zero tolerance for blocked ramps.",
               relevant_categories=["accessibility"], priority=1),
        Policy(id=str(uuid.uuid4()), title="Road Hazard Response", category="road",
               content="Road hazards on major arteries require immediate response. Secondary roads within 4 hours. Fallen trees, debris, and damaged signage are priority categories.",
               relevant_categories=["road"], priority=1),
    ]
    db.add_all(policies)

    await db.commit()
    return {"status": "seeded", "districts": len(districts), "teams": len(teams), "infrastructure": len(infra_items)}
