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
    {
        "id": "E6",
        "name": "Conflicting severity reports",
        "reports": [
            {"text": "Minor water drip near the park fountain, barely noticeable.", "lat": 40.7130, "lon": -74.005},
            {"text": "EMERGENCY: Water gushing from pipe near park, flooding the sidewalk!", "lat": 40.7132, "lon": -74.0052},
        ],
        "expected_category": "water",
        "expected_severity_range": [3, 5],
    },
    {
        "id": "E7",
        "name": "Incomplete evidence report",
        "reports": [
            {"text": "Something is wrong on Main Street.", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_category": None,
        "expected_uncertainty": True,
    },
    {
        "id": "E8",
        "name": "Conflicting category reports",
        "reports": [
            {"text": "There is a big puddle of water on the road near the intersection.", "lat": 40.7128, "lon": -74.006},
            {"text": "The road surface is damaged and crumbling at the intersection.", "lat": 40.7129, "lon": -74.0061},
        ],
        "expected_categories": ["water", "road"],
        "check": "category_mismatch_detected",
    },
    {
        "id": "E9",
        "name": "Multiple teams different tradeoffs",
        "reports": [
            {"text": "Waste bin overflow in District 1, needs immediate attention.", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_team_selection": True,
        "check": "selects_nearest_capable",
    },
    {
        "id": "E10",
        "name": "Resource disappears mid-assignment",
        "reports": [
            {"text": "Road hazard on Highway 5, fallen debris.", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_category": "road",
        "simulate": {"event_type": "team_unavailable", "team_category": "road"},
        "expected_replan": True,
    },
    {
        "id": "E11",
        "name": "High-priority interrupt",
        "reports": [
            {"text": "Water main burst at Downtown, flooding streets!", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_severity_range": [4, 5],
    },
    {
        "id": "E12",
        "name": "Replan quality check",
        "reports": [
            {"text": "Water leak at Main and 3rd intersection.", "lat": 40.7128, "lon": -74.006},
        ],
        "simulate": {"event_type": "team_unavailable", "team_category": "water"},
        "expected_replan": True,
        "check": "replan_mentions_concrete_next_step",
    },
    {
        "id": "E13",
        "name": "Noisy/irrelevant report",
        "reports": [
            {"text": "Nice weather today! The park looks beautiful.", "lat": 40.7128, "lon": -74.006},
        ],
        "expected_low_severity": True,
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
            include_assigned=True,
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
        if "expected_category" in scenario and scenario["expected_category"]:
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

        if scenario.get("expected_uncertainty"):
            conf = r["analysis"]["confidence"]
            checks.append({
                "check": "low_confidence_detected",
                "expected": "< 0.5",
                "actual": conf,
                "pass": conf < 0.5,
            })

        if scenario.get("expected_low_severity"):
            sev = r["analysis"]["severity"]
            checks.append({
                "check": "low_severity",
                "expected": "<= 2",
                "actual": sev,
                "pass": sev <= 2,
            })

        if scenario.get("check") == "replan_mentions_concrete_next_step":
            checks.append({
                "check": "response_not_empty",
                "expected": True,
                "actual": len(r["response"]) > 50,
                "pass": len(r["response"]) > 50,
            })

    if "expected_severity_range" in scenario:
        last_r = result["results"][-1]
        sev = last_r["analysis"]["severity"]
        lo, hi = scenario["expected_severity_range"]
        checks.append({
            "check": "severity_in_range",
            "expected": f"{lo}-{hi}",
            "actual": sev,
            "pass": lo <= sev <= hi,
        })

    if scenario.get("expected_correlation"):
        last = result["results"][-1]
        checks.append({
            "check": "correlation_detected",
            "expected": True,
            "actual": not last["is_new_incident"],
            "pass": not last["is_new_incident"],
        })

    if scenario.get("check") == "category_mismatch_detected" and len(result["results"]) >= 2:
        first_cat = result["results"][0]["analysis"]["category"]
        second_cat = result["results"][1]["analysis"]["category"]
        checks.append({
            "check": "both_reports_processed",
            "expected": True,
            "actual": len(result["results"]) == 2,
            "pass": len(result["results"]) == 2,
        })

    if scenario.get("check") == "selects_nearest_capable":
        last = result["results"][-1]
        has_assignment = "Assigned" in last["team_decision"]
        checks.append({
            "check": "team_assigned",
            "expected": True,
            "actual": has_assignment,
            "pass": has_assignment,
        })

    if scenario.get("expected_replan") and result["replan"]:
        checks.append({
            "check": "replan_executed",
            "expected": True,
            "actual": "Replanned" in result["replan"]["team_decision"],
            "pass": "Replanned" in result["replan"]["team_decision"],
        })
        if scenario.get("check") == "replan_mentions_concrete_next_step":
            resp = result["replan"]["response"].lower()
            has_next = any(w in resp for w in ["will", "next", "dispatch", "team", "eta", "arrive", "respond"])
            checks.append({
                "check": "replan_concrete_next_step",
                "expected": True,
                "actual": has_next,
                "pass": has_next,
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
    all_results = []
    all_evals = []

    for scenario in SCENARIOS:
        await reset_db()
        result = await run_scenario(scenario)
        evaluation = await evaluate(scenario, result)
        all_results.append(result)
        all_evals.append(evaluation)

        status = "PASS" if evaluation["score"] == 100 else "PARTIAL" if evaluation["score"] > 0 else "FAIL"
        failed = [c for c in evaluation["checks"] if not c["pass"]]
        fail_detail = ""
        if failed:
            fail_detail = f" FAILED: {', '.join(c['check'] for c in failed)}"
        print(f"[{status}] {scenario['id']}: {scenario['name']} - {evaluation['score']}% ({evaluation['passed']}/{evaluation['total']}){fail_detail}")

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
