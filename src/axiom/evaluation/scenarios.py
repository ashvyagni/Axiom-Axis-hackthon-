import asyncio
import json
import time
from axiom.db.engine import engine, async_session, Base
from axiom.world.seed import seed_city
from axiom.api.orchestrator import orchestrator
from axiom.tools.registry import registry


SCENARIOS = [
    {
        "id": "E1",
        "name": "Simple waste incident",
        "reports": [
            {"text": "The garbage container near District 2 is overflowing.", "lat": 40.7158, "lon": -74.002},
        ],
        "expected_category": "waste",
        "expected_skill": "waste_management",
        "expected_team_assignment": True,
    },
    {
        "id": "E2",
        "name": "Duplicate reports",
        "reports": [
            {"text": "Garbage piling up near the market in Riverside.", "lat": 40.7160, "lon": -74.0018},
            {"text": "Same issue - overflowing bins near Riverside market.", "lat": 40.7159, "lon": -74.0022},
            {"text": "The trash situation by the market is getting worse.", "lat": 40.7157, "lon": -74.0025},
        ],
        "expected_category": "waste",
        "expected_correlation": True,
    },
    {
        "id": "E3",
        "name": "Resource failure + replan",
        "reports": [
            {"text": "Water leak at Main and 3rd, seems serious.", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_category": "water",
        "expected_skill": "water_infrastructure",
        "simulate": {"event_type": "team_unavailable", "team_category": "water"},
        "expected_replan": True,
    },
    {
        "id": "E4",
        "name": "Accessibility obstruction",
        "reports": [
            {"text": "Wheelchair ramp at City Hall is blocked by construction debris.", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_category": "accessibility",
        "expected_skill": "accessibility",
    },
    {
        "id": "E5",
        "name": "Road hazard",
        "reports": [
            {"text": "Fallen tree blocking the main road in Downtown Core.", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_category": "road",
        "expected_skill": "road_incident",
    },
]


async def reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as db:
        await seed_city(db)


async def run_scenario(scenario: dict) -> dict:
    start = time.time()
    results = []

    for report in scenario["reports"]:
        r = await orchestrator.process_report(
            text=report["text"],
            latitude=report["lat"],
            longitude=report["lon"],
        )
        results.append(r)

    replan_result = None
    if "simulate" in scenario:
        teams = await registry.execute(
            "get_available_teams",
            category=scenario["simulate"].get("team_category"),
            latitude=scenario["reports"][0]["lat"],
            longitude=scenario["reports"][0]["lon"],
        )
        if teams.success and teams.data.get("teams"):
            tid = teams.data["teams"][0]["id"]
            await registry.execute("simulate_event", event_type=scenario["simulate"]["event_type"], parameters={"team_id": tid})
            if results:
                replan_result = await orchestrator.replan_for_incident(results[-1]["incident_id"])

    total_time = int((time.time() - start) * 1000)

    return {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "reports_processed": len(results),
        "results": results,
        "replan": replan_result,
        "total_time_ms": total_time,
    }


async def evaluate(scenario: dict, result: dict) -> dict:
    checks = []

    for r in result["results"]:
        if "expected_category" in scenario:
            checks.append({
                "check": "category_match",
                "expected": scenario["expected_category"],
                "actual": r["analysis"]["category"],
                "pass": r["analysis"]["category"] == scenario["expected_category"],
            })

        if "expected_skill" in scenario:
            checks.append({
                "check": "skill_match",
                "expected": scenario["expected_skill"],
                "actual": r["skill"],
                "pass": r["skill"] == scenario["expected_skill"],
            })

        if scenario.get("expected_team_assignment"):
            checks.append({
                "check": "team_assigned",
                "expected": True,
                "actual": "Assigned" in r["team_decision"],
                "pass": "Assigned" in r["team_decision"],
            })

    if scenario.get("expected_correlation"):
        last = result["results"][-1]
        checks.append({
            "check": "correlation_detected",
            "expected": True,
            "actual": not last["is_new_incident"],
            "pass": not last["is_new_incident"],
        })

    if scenario.get("expected_replan") and result["replan"]:
        checks.append({
            "check": "replan_executed",
            "expected": True,
            "actual": "Replanned" in result["replan"]["team_decision"],
            "pass": "Replanned" in result["replan"]["team_decision"],
        })

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)

    return {
        "scenario_id": scenario["id"],
        "checks": checks,
        "passed": passed,
        "total": total,
        "score": round(passed / total * 100, 1) if total > 0 else 0,
    }


async def run_baseline():
    await reset_db()

    all_results = []
    all_evals = []

    for scenario in SCENARIOS:
        await reset_db()
        result = await run_scenario(scenario)
        evaluation = await evaluate(scenario, result)
        all_results.append(result)
        all_evals.append(evaluation)

        status = "PASS" if evaluation["score"] == 100 else "PARTIAL"
        print(f"[{status}] {scenario['id']}: {scenario['name']} - {evaluation['score']}% ({evaluation['passed']}/{evaluation['total']})")

    total_checks = sum(e["total"] for e in all_evals)
    total_passed = sum(e["passed"] for e in all_evals)
    overall_score = round(total_passed / total_checks * 100, 1) if total_checks > 0 else 0

    print(f"\n{'='*60}")
    print(f"V1 BASELINE: {total_passed}/{total_checks} checks passed ({overall_score}%)")
    print(f"{'='*60}")

    return {
        "baseline": True,
        "overall_score": overall_score,
        "total_checks": total_checks,
        "total_passed": total_passed,
        "scenarios": all_evals,
    }


if __name__ == "__main__":
    asyncio.run(run_baseline())
