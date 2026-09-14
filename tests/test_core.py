def test_config_loads():
    from axiom.config import get_settings
    s = get_settings()
    assert s.ENVIRONMENT in ("development", "production", "testing")
    assert s.GROQ_MODEL_STRONG
    assert s.PRISMTRACE_HOST


def test_tool_registry_has_tools():
    from axiom.tools.registry import registry
    tools = registry.list_tools()
    names = [t["name"] for t in tools]
    assert "get_city_state" in names
    assert "create_incident" in names
    assert "get_available_teams" in names
    assert "assign_team" in names
    assert "retrieve_policy" in names


def test_skill_registry_has_skills():
    from axiom.skills.registry import skill_registry
    skills = skill_registry.list_skills()
    names = [s["name"] for s in skills]
    assert "waste_management" in names
    assert "water_infrastructure" in names
    assert "verification" in names
