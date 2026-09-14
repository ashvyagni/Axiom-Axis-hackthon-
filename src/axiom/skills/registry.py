from pydantic import BaseModel
from typing import Any


class SkillDefinition(BaseModel):
    name: str
    purpose: str
    allowed_tools: list[str]
    system_instructions: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    verification_required: bool = True


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition):
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition | None:
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "purpose": s.purpose} for s in self._skills.values()]

    def get_tools_for_skill(self, name: str) -> list[str]:
        skill = self._skills.get(name)
        return skill.allowed_tools if skill else []


skill_registry = SkillRegistry()


SKILLS = [
    SkillDefinition(
        name="waste_management",
        purpose="Handle waste overflow, missed collection, and waste accumulation incidents",
        allowed_tools=["get_city_state", "get_incident", "search_incidents", "create_incident",
                       "correlate_incidents", "get_available_teams", "assign_team",
                       "update_incident_status", "retrieve_policy", "verify_resolution"],
        system_instructions="""You are a waste management specialist for AXIOM city operations.
When handling waste incidents:
- Classify the waste type (overflow, collection miss, accumulation)
- Check for duplicate reports in the area
- Assess severity based on volume, location sensitivity, and health risk
- Select appropriate waste management teams
- Reference waste collection schedules and policies
- Verify resolution by confirming collection occurred""",
        input_schema={"incident_description": "string", "location": "object"},
        output_schema={"action": "string", "team": "string", "priority": "integer"},
    ),
    SkillDefinition(
        name="water_infrastructure",
        purpose="Handle water leaks, pipe bursts, and water infrastructure faults",
        allowed_tools=["get_city_state", "get_incident", "search_incidents", "create_incident",
                       "correlate_incidents", "get_available_teams", "assign_team",
                       "update_incident_status", "retrieve_policy", "verify_resolution"],
        system_instructions="""You are a water infrastructure specialist for AXIOM city operations.
When handling water incidents:
- Assess leak severity and potential damage
- Check nearby infrastructure status
- Prioritize based on water loss, property risk, and public safety
- Select teams with plumbing/water infrastructure capability
- Reference emergency water shutoff protocols
- Verify resolution by confirming leak is contained""",
        input_schema={"incident_description": "string", "location": "object"},
        output_schema={"action": "string", "team": "string", "priority": "integer"},
    ),
    SkillDefinition(
        name="accessibility",
        purpose="Handle accessibility obstructions and ensure ADA compliance",
        allowed_tools=["get_city_state", "get_incident", "search_incidents", "create_incident",
                       "get_available_teams", "assign_team", "update_incident_status",
                       "retrieve_policy", "verify_resolution"],
        system_instructions="""You are an accessibility compliance specialist for AXIOM city operations.
When handling accessibility incidents:
- Identify the specific accessibility barrier
- Check relevant ADA/accessibility policies
- Prioritize based on impact on disabled residents
- Select appropriate teams for removal/repair
- Reference accessibility regulations and compliance requirements
- Verify resolution by confirming pathway is clear""",
        input_schema={"incident_description": "string", "location": "object"},
        output_schema={"action": "string", "team": "string", "priority": "integer"},
    ),
    SkillDefinition(
        name="road_incident",
        purpose="Handle road hazards, obstructions, and traffic incidents",
        allowed_tools=["get_city_state", "get_incident", "search_incidents", "create_incident",
                       "correlate_incidents", "get_available_teams", "assign_team",
                       "update_incident_status", "retrieve_policy", "verify_resolution"],
        system_instructions="""You are a road incident specialist for AXIOM city operations.
When handling road incidents:
- Assess traffic impact and safety risk
- Check for related incidents nearby
- Prioritize based on road type, traffic volume, and hazard severity
- Select teams with road/traffic capability
- Reference traffic management protocols
- Verify resolution by confirming hazard is cleared""",
        input_schema={"incident_description": "string", "location": "object"},
        output_schema={"action": "string", "team": "string", "priority": "integer"},
    ),
    SkillDefinition(
        name="resource_dispatch",
        purpose="Select and dispatch the optimal team/resource for an assignment",
        allowed_tools=["get_available_teams", "get_team_details", "assign_team", "get_city_state"],
        system_instructions="""You are a resource dispatch coordinator for AXIOM city operations.
When dispatching resources:
- Consider team capabilities and proficiency
- Factor in distance and ETA
- Check team availability and current workload
- Optimize for response time and capability match
- Consider priority of the incident
- Assign the best-fit team""",
        input_schema={"incident_id": "string", "category": "string", "latitude": "number", "longitude": "number"},
        output_schema={"team_id": "string", "eta_minutes": "integer"},
    ),
    SkillDefinition(
        name="policy_intelligence",
        purpose="Retrieve and interpret relevant policies, SOPs, and operational information",
        allowed_tools=["retrieve_policy", "get_city_state"],
        system_instructions="""You are a policy intelligence specialist for AXIOM city operations.
When retrieving policies:
- Match incident category to relevant policy domains
- Extract actionable guidance from policy text
- Identify constraints and requirements
- Reference specific policy sections
- Flag any policy conflicts or ambiguities""",
        input_schema={"category": "string", "context": "string"},
        output_schema={"policies": "array", "guidance": "string"},
    ),
    SkillDefinition(
        name="verification",
        purpose="Verify whether incident resolution was actually achieved",
        allowed_tools=["verify_resolution", "get_incident", "get_city_state"],
        system_instructions="""You are a verification specialist for AXIOM city operations.
When verifying resolution:
- Compare expected outcome against observed evidence
- Check if the root cause was addressed
- Verify that the fix is sustainable
- Classify verification status: supported, contradicted, uncertain, insufficient evidence
- Recommend follow-up actions if verification fails""",
        input_schema={"incident_id": "string", "expected": "string", "observed": "string"},
        output_schema={"status": "string", "confidence": "number"},
    ),
]

for skill in SKILLS:
    skill_registry.register(skill)
