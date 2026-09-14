# AXIOM — Master Project Context & Implementation Blueprint

**For: Antigravity (Senior AI Engineering Agent)**
**From: OpenCode (Prior Development Agent)**
**Date: September 14, 2026**
**Repo: https://github.com/ashvyagni/Axiom-Axis-hackthon-.git**

---

## 1. CORE VISION & HACKATHON GOALS

### What is AXIOM?

AXIOM is an **AI operational supervisor** for city operations. It is NOT a chatbot, NOT a ticketing wrapper, NOT a dashboard with AI bolted on. It is a system where **AI operates within a changing environment**: it observes signals, reasons over state, decides what to do, acts through real database tools, verifies outcomes, and adapts when conditions change.

### The "Wow Factor" for Judges

The single differentiating demonstration is:

> **A citizen reports a water leak. AXIOM classifies it, dispatches a team. Then the team becomes unavailable. AXIOM detects the stale plan, replans, assigns an alternative team, and explains what happened — all while PRISM captures every decision as a trace.**

This proves AXIOM is not a static classifier — it is an **adaptive operational intelligence system**.

### Hackathon Track

**AI for Smart Cities** — ForgeAI Hackathon 2026

### Judging Criteria Alignment

| Criterion | Weight | What We Deliver |
|-----------|--------|-----------------|
| Technical Implementation | 25% | Full agent loop, 13 DB tools, 7 skills, PostgreSQL, PRISM spans |
| PRISM Evaluation | 20% | 133 traces captured, V1→V2 improvement measured |
| AI Improvement | 20% | 92.3% → 100% (27/27 checks), concrete engineering changes |
| Innovation | 10% | Adaptive replanning, uncertainty detection, weather-aware decisions |
| Impact | 10% | Real operational intelligence pattern applicable to any city |
| Demo | 15% | Live dashboard, scripted demo scenario, PRISM trace walkthrough |

---

## 2. ARCHITECTURE & DESIGN DECISIONS

### High-Level Flow

```
Citizen Report (text/image + location)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                       │
│                                                      │
│  1. UNDERSTAND ─── LLM classifies incident          │
│  2. PLAN ───────── Deterministic priority/risks     │
│  3. SEARCH ─────── Find similar incidents (2km)     │
│  4. CREATE/MERGE ─ New incident or add evidence     │
│  5. POLICY ─────── Retrieve applicable policies     │
│  6. DISPATCH ───── Select & assign team              │
│  7. VERIFY ─────── Check outcome                     │
│  8. RESPOND ────── Natural language to operator      │
│                                                      │
│  Each step → PRISM span with timing                 │
│  Final run → PRISM trace with evaluation             │
│                                                      │
└─────────────────────────────────────────────────────┘
        │
        ▼
   PostgreSQL (world state)
   PRISM (observability)
   Frontend (dashboard)
```

### Key Design Decisions

1. **Single orchestrator, modular skills** — One `Orchestrator` class drives the loop. Skills define domain knowledge but the orchestrator doesn't dynamically dispatch to them (it selects skill name for metadata only).

2. **Deterministic tools, probabilistic reasoning** — Tools do real DB operations. LLM classifies and generates responses. Hard constraints (distance, availability) are enforced in code.

3. **Heuristic uncertainty override** — LLM often gives false high confidence on vague reports. A regex-based heuristic (`_heuristic_uncertainty`) forces confidence < 0.5 for vague/short/subjective text.

4. **Weather as context, not trigger** — Live weather from Open-Meteo is injected into the classification prompt only when adverse. It influences severity but doesn't trigger incidents.

5. **PRISM via HTTP, not SDK** — The `prismtrace-sdk` is installed but unused. All tracing goes through raw `httpx` POST to PRISM API. The SDK import is dead code.

6. **No WebSocket yet** — Dashboard polls every 10 seconds. No real-time updates.

### File Structure

```
AxiomAI/
├── frontend/index.html          # Single-file SPA dashboard (862 lines)
├── src/axiom/
│   ├── api/orchestrator.py      # Core agent loop (679 lines) ← THE BRAIN
│   ├── ai/
│   │   ├── base.py              # AIProvider ABC
│   │   └── groq.py              # GroqCloud implementation
│   ├── db/
│   │   ├── engine.py            # SQLAlchemy async engine
│   │   └── models/domain.py     # 13 ORM models, 3 enums
│   ├── tools/
│   │   ├── registry.py          # ToolRegistry singleton
│   │   └── implementations/core_tools.py  # 12 tools
│   ├── skills/registry.py       # 7 skills (mostly metadata)
│   ├── observability/prism.py   # PRISM adapter with span support
│   ├── evaluation/scenarios.py  # 13 scenarios, E1-E13
│   ├── world/
│   │   ├── seed.py              # City seed data
│   │   ├── weather.py           # Open-Meteo live weather
│   │   └── provider.py          # CityDataProvider ABC
│   ├── demo.py                  # 6 demo scenarios
│   ├── config.py                # Pydantic settings
│   └── main.py                  # FastAPI app (13 routes)
├── tests/
│   ├── test_core.py             # 3 tests
│   └── test_tools.py            # 3 tests (haversine only)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. DATABASE SCHEMA (Complete)

### Enums

```python
IncidentCategory: waste | water | accessibility | road
IncidentStatus: reported | acknowledged | assigned | dispatched | in_progress | resolved | failed | escalated
TeamStatus: available | assigned | dispatched | unavailable
```

### Core Tables

**incidents** — The central entity
- `id` (UUID PK), `category`, `severity` (1-5), `confidence` (0-1), `description`, `status`, `latitude`, `longitude`, `district_id` (FK nullable), `created_at`, `updated_at`, `resolved_at`, `resolution_notes`, `metadata_json` (JSON)
- Relationships: `reports` (1:N), `assignments` (1:N), `evidence` (1:N)

**reports** — Citizen-submitted reports attached to incidents
- `id` (UUID PK), `incident_id` (FK), `text`, `image_url` (nullable), `latitude`, `longitude`, `source_type`, `created_at`

**teams** — Response teams
- `id` (UUID PK), `name`, `status` (TeamStatus), `latitude`, `longitude`, `current_assignment_id` (nullable), `created_at`
- Relationships: `capabilities` (1:N), `assignments` (1:N)

**team_capabilities** — What each team can handle
- `id` (UUID PK), `team_id` (FK), `category`, `proficiency` (1-5)

**assignments** — Team-to-incident linkage
- `id` (UUID PK), `team_id` (FK), `incident_id` (FK), `status`, `eta_minutes`, `assigned_at`, `dispatched_at`, `completed_at`

**districts** — City areas
- `id` (UUID PK), `name`, `latitude`, `longitude`, `population`, `priority`

**infrastructure** — City assets
- `id` (UUID PK), `name`, `type` (water/electricity/waste/road/accessibility), `district_id` (FK), `latitude`, `longitude`, `status`, `metadata_json`

**policies** — Operational policies
- `id` (UUID PK), `title`, `category`, `content`, `relevant_categories` (JSON), `priority`

**agent_runs** — AXIOM execution records
- `id` (UUID PK), `incident_id` (FK nullable), `session_id`, `status`, `skill_used`, `started_at`, `completed_at`, `outcome`, `metadata_json`

**incident_relations** — Links between related incidents
- `id` (UUID PK), `incident_a_id` (FK), `incident_b_id` (FK), `relation_type`, `created_at`

**verification_results** — Outcome verification
- `id` (UUID PK), `incident_id` (FK), `expected_outcome`, `observed_outcome`, `status`, `evidence` (JSON), `verified_at`

**world_state_changes** — Audit log
- `id` (UUID PK), `entity_type`, `entity_id`, `field`, `old_value`, `new_value`, `cause`, `created_at`

### Seed Data (world/seed.py)

**4 Districts:** Downtown Core (pop 50000), Riverside (pop 35000), Hillcrest (pop 25000), Industrial Zone (pop 15000)

**20 Infrastructure:** 5 per district — mix of water, electricity, waste, road, accessibility types

**4 Teams:**
- Alpha Response — capabilities: waste, water — location: Downtown
- Bravo Services — capabilities: water, road — location: Riverside
- Charlie Maintenance — capabilities: waste, accessibility — location: Hillcrest
- Delta Emergency — capabilities: road, accessibility — location: Industrial

**4 Policies:** Waste Collection SOP, Water Emergency Response, Accessibility Compliance, Road Hazard Protocol

---

## 4. THE 2D CITY RENDERER (Detailed Spec)

### Current State

The City view (tab 5) currently shows a **static grid of district cards and infrastructure cards**. There is NO map, NO visualization, NO spatial rendering. This is the single biggest missing visual feature.

### Target Design

A **2D operational map** showing the city as a grid of districts with real-time incident markers, team positions, and infrastructure status. Think: a simplified tactical operations map.

### Technical Implementation

**Technology:** HTML5 Canvas (not SVG — Canvas is better for real-time updates and many elements)

**Layout:**
```
┌─────────────────────────────────────────────┐
│  2D City Operations Map                      │
│                                              │
│  ┌──────────┬──────────┐                     │
│  │Downtown  │Riverside │  ← District grid    │
│  │ Core     │          │    (2x2 layout)     │
│  │          │          │                     │
│  ├──────────┼──────────┤                     │
│  │Hillcrest │Industrial│                     │
│  │          │  Zone    │                     │
│  └──────────┴──────────┘                     │
│                                              │
│  Legend: ● Incident  ■ Team  ▲ Infrastructure│
│          ●=critical ■=available ▲=operational│
└─────────────────────────────────────────────┘
```

**Canvas Dimensions:** 800x600px (responsive via CSS)

**District Rendering:**
- Each district = rounded rectangle, 380x260px with 20px gap
- Fill: dark graphite (#1a1a2e) with subtle border (#2a2a4a)
- District name: centered, white, 14px Inter font
- Population: small gray text below name
- Active incident count: badge in top-right corner (red if > 0)

**Incident Markers:**
- Rendered as pulsing circles on the canvas
- Position: calculated from lat/lon relative to district center
- Color by severity: green(1), cyan(2), yellow(3), orange(4), red(5)
- Size: 12px radius
- Animation: subtle pulse (opacity 0.6 → 1.0 → 0.6)
- On hover: show tooltip with category, severity, description
- On click: open incident detail panel

**Team Markers:**
- Rendered as squares
- Color: green=available, yellow=assigned, red=unavailable
- Position: at team lat/lon
- Size: 10x10px
- Label: team initials (A, B, C, D)
- If assigned: draw line from team to incident (dashed, category-colored)

**Infrastructure Markers:**
- Rendered as triangles
- Color: green=operational, yellow=maintenance, red=failed
- Size: 8px
- On hover: show infrastructure name and status

**Interaction:**
- Hover over any marker → tooltip with details
- Click incident → show detail panel (existing right sidebar)
- Click team → show team info
- Click district → filter incidents to that district

### Data Flow

```
GET /api/city-state → districts, infrastructure
GET /api/incidents → active incidents with lat/lon
GET /api/teams → team positions and status
        │
        ▼
   Canvas render loop (60fps)
        │
        ▼
   Draw districts → infrastructure → incidents → teams
```

### API Changes Needed

Add a new endpoint that returns all spatial data in one call:

```python
@app.get("/api/city/spatial")
async def city_spatial():
    # Returns all districts, incidents, teams, infrastructure
    # with lat/lon for canvas rendering
```

Or reuse existing endpoints (they already return lat/lon).

### Implementation Notes

1. Use `requestAnimationFrame` for smooth rendering
2. Only re-render when data changes (not every frame)
3. Implement a simple spatial hash for hover detection
4. Keep the canvas in the City tab content area
5. Add a "Refresh" button and auto-refresh on data change
6. District boundaries are approximate (rectangles) — don't try to make them geographically accurate

---

## 5. MISSING FEATURES & GAPS

### HIGH PRIORITY (Must fix for demo)

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| 1 | **City view is static cards, not a map** | `frontend/index.html` view 5 | Implement 2D Canvas renderer (see Section 4) |
| 2 | **Evaluation view is hardcoded** | `frontend/index.html` view 6 | Fetch from `/api/scores/summary` or compute locally |
| 3 | **No `/api/reset` endpoint** | `main.py` | Add endpoint that drops/recreates tables and re-seeds |
| 4 | **Span finishing bug in orchestrator** | `orchestrator.py:125-128` | The `finish_span` call is dead code (spans is always empty at that point). Remove it or fix the span lifecycle |
| 5 | **Demo scenario state mutation** | `demo.py` | `run_full_demo()` mutates scenario steps in place. Deep-copy steps before modifying |
| 6 | **Status filter values wrong** | `frontend/index.html` | Filter offers "open" but actual statuses are "reported", "acknowledged", etc. |
| 7 | **City view references `area_km2`** | `frontend/index.html` | District model has no `area_km2`. Remove or add field |

### MEDIUM PRIORITY (Improves demo quality)

| # | Issue | Fix |
|---|-------|-----|
| 8 | **No WebSocket/SSE for real-time** | Add SSE endpoint for incident updates, or keep polling |
| 9 | **`run_full_demo` uses blocking `time.sleep`** | Change to `await asyncio.sleep(1)` |
| 10 | **`GROQ_MODEL_VISION` set to text model** | Set to actual vision model or remove image analysis |
| 11 | **`retrieve_policy` ignores `context` param** | Either use it in query or remove from signature |
| 12 | **`assign_team` can regress incident status** | Check current status before overwriting |
| 13 | **Correlation doesn't check reverse direction** | Add reverse check in `correlate_incidents` |
| 14 | **No error handling in frontend `Promise.all`** | Use `Promise.allSettled` instead |

### LOW PRIORITY (Nice to have)

| # | Issue | Fix |
|---|-------|-----|
| 15 | `Scenario` model never used | Remove or use for persistent scenario storage |
| 16 | `ToolCall` model never used | Either write tool calls to DB or remove model |
| 17 | `IncidentEvidence` model never used | Either populate it or remove relationship |
| 18 | `schemas/` package empty | Add Pydantic request/response schemas |
| 19 | `scripts/` empty | Add utility scripts (seed, reset, benchmark) |
| 20 | No Alembic migrations | Fine for hackathon, but note for production |
| 21 | No API auth | Fine for hackathon demo |
| 22 | No rate limiting | Fine for hackathon demo |

---

## 6. ALL API ENDPOINTS (Complete Reference)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | No | Health check: `{"name":"AXIOM","version":"0.1.0","status":"operational"}` |
| `GET` | `/dashboard` | No | Serves `frontend/index.html` |
| `GET` | `/api/tools` | No | Lists all registered tools |
| `GET` | `/api/skills` | No | Lists all registered skills |
| `POST` | `/api/report` | No | **Main entry point.** Body: `{text, image_url?, latitude, longitude}`. Returns full orchestrator result |
| `GET` | `/api/incidents` | No | List incidents. Query: `category?, status?` |
| `GET` | `/api/incidents/{id}` | No | Get incident detail |
| `GET` | `/api/teams` | No | List teams. Query: `category?` |
| `GET` | `/api/city-state` | No | Get districts + infrastructure |
| `POST` | `/api/simulate` | No | Trigger event. Body: `{event_type, parameters}` |
| `POST` | `/api/replan/{id}` | No | Replan for incident |
| `GET` | `/api/runs` | No | List recent agent runs (last 20) |
| `GET` | `/api/weather` | No | Get weather. Query: `latitude, longitude` |
| `GET` | `/api/demo/scenarios` | No | List available demo scenarios |
| `POST` | `/api/demo/run/{name}` | No | Run a demo scenario (resets DB!) |

### Key Request/Response Shapes

**POST /api/report** — Request:
```json
{
  "text": "Water leak at Main and 3rd",
  "image_url": null,
  "latitude": 40.7128,
  "longitude": -74.006
}
```

**POST /api/report** — Response:
```json
{
  "run_id": "uuid",
  "incident_id": "uuid",
  "response": "Classification: Critical water leak...",
  "analysis": {
    "category": "water",
    "severity": 5,
    "confidence": 1.0,
    "description": "Water leak detected...",
    "uncertainty_reason": null
  },
  "skill": "water_infrastructure",
  "team_decision": "Assigned Bravo Services (ETA: 1 min)",
  "latency_ms": 1590,
  "is_new_incident": true,
  "correlated_with": [],
  "tool_calls": [
    {"tool": "search_incidents", "result": "Found 0 similar incidents"},
    {"tool": "create_incident", "result": "Created incident uuid"},
    {"tool": "get_available_teams", "result": "Found 2 teams"},
    {"tool": "assign_team", "result": "Assigned Bravo Services (ETA: 1 min)"},
    {"tool": "retrieve_policy", "result": "Found 1 policies"}
  ],
  "uncertainty_reason": null
}
```

---

## 7. ORCHESTRATOR FLOW (Exact Step Sequence)

### process_report(text, image_url, latitude, longitude)

```
1.  Create AgentRun record (status=running)
2.  Search for similar incidents within 2km (search_incidents tool)
3.  Get existing reports for found incidents (get_incident tool)
4.  CLASSIFY (LLM call via _understand):
    - Build context from existing reports
    - Fetch weather data (Open-Meteo)
    - If adverse weather → add alert context
    - LLM classifies: category, severity, confidence
    - Apply heuristic uncertainty override (regex)
    - Return analysis dict
5.  [DEAD CODE: span finishing attempt — remove]
6.  Create understand_report PRISM span
7.  If category == "noise" → early return
8.  Retrieve policies for category (retrieve_policy tool)
9.  GENERATE PLAN (deterministic):
    - Compute priority from severity
    - Identify risk factors (weather, confidence, existing incidents)
    - Return plan with steps and expected outcome
10. Handle incident:
    a. If similar incidents exist:
       - Add report to first incident
       - If new severity > old → escalate severity
       - If multiple incidents → correlate
    b. If no similar incidents:
       - Create new incident (create_incident tool)
11. DISPATCH (conditional on confidence ≥ 0.4):
    a. Get available teams (get_available_teams tool)
    b. Try to assign first team (assign_team tool)
    c. If fails → try alternatives
    d. If confidence < 0.4 → HOLD
12. VERIFY OUTCOME (if team assigned):
    - Check incident status
    - If failed → flag for replan
13. GENERATE RESPONSE (LLM call):
    - Build prompt with analysis, team decision, policy, correlation, uncertainty
    - Generate 2-3 sentence response
14. Update AgentRun (status=completed, outcome, metadata)
15. Send PRISM trace with all spans
16. Return full result dict
```

### replan_for_incident(incident_id)

```
1.  Load incident from DB
2.  Get available teams (include_assigned=True)
3.  Try assignment loop (skip unavailable teams)
4.  Generate replan response (LLM)
5.  Send PRISM trace
6.  Return result
```

---

## 8. ALL TOOLS (Complete Reference)

| # | Tool Name | Input | What It Does | Returns |
|---|-----------|-------|--------------|---------|
| 1 | `get_city_state` | `district_id?` | Aggregated city view | districts, infrastructure |
| 2 | `get_incident` | `incident_id` | Single incident + report count | incident detail |
| 3 | `search_incidents` | `category?, status?, district_id?, latitude?, longitude?, radius_km?` | Search with haversine filter | incidents list, count |
| 4 | `create_incident` | `category, severity, confidence, description, latitude, longitude, district_id?` | Create new incident | id, status, message |
| 5 | `correlate_incidents` | `incident_ids[], relation_type?` | Link related incidents | correlated pairs |
| 6 | `get_available_teams` | `category?, latitude?, longitude?, include_assigned?` | Teams sorted by distance | teams list, count |
| 7 | `get_team_details` | `team_id` | Single team with capabilities | team detail |
| 8 | `assign_team` | `team_id, incident_id` | Assign team, update statuses, create assignment, record state change | assignment_id, eta |
| 9 | `update_incident_status` | `incident_id, new_status, reason?` | Update status, set resolved_at | old/new status |
| 10 | `retrieve_policy` | `category, context?` | Find policies for category | policies list |
| 11 | `verify_resolution` | `incident_id, expected_outcome, observed_outcome` | Create verification record | status |
| 12 | `simulate_event` | `event_type, parameters` | team_unavailable or infrastructure_failure | event result |

---

## 9. ALL SKILLS (Complete Reference)

| # | Skill | Purpose | Allowed Tools |
|---|-------|---------|---------------|
| 1 | `waste_management` | Waste overflow, collection | All 10 core tools |
| 2 | `water_infrastructure` | Leaks, pipes, flooding | All 10 core tools |
| 3 | `accessibility` | ADA compliance, obstructions | All 10 core tools |
| 4 | `road_incident` | Hazards, obstructions, traffic | All 10 core tools |
| 5 | `resource_dispatch` | Team selection optimization | get_available_teams, get_team_details, assign_team, get_city_state |
| 6 | `policy_intelligence` | Policy interpretation | retrieve_policy, get_city_state |
| 7 | `verification` | Outcome verification | verify_resolution, get_incident, get_city_state |

**IMPORTANT:** Skills are registered but NEVER dynamically invoked. The orchestrator calls `_select_skill(category)` which returns a name string stored in `AgentRun.skill_used`. The skill's `system_instructions`, `allowed_tools`, and schemas are NOT used to constrain orchestrator behavior. The orchestrator directly calls tools.

---

## 10. PRISM INTEGRATION (Complete Reference)

### What Gets Traced

Every `process_report()` and `replan_for_incident()` call sends:

**1. Trace** (POST `/api/traces`):
```json
{
  "project_id": "61b7b4c9-386d-492e-9b71-d4442ba08454",
  "model": "allam-2-7b",
  "input_messages": [{"role": "user", "content": "original report text"}],
  "output_message": "AXIOM's response",
  "latency_ms": 1590,
  "session_id": "run-98bd8af9",
  "agent_id": "axiom-orchestrator",
  "agent_name": "AXIOM",
  "metadata": {
    "incident_id": "uuid",
    "skill": "water_infrastructure",
    "category": "water",
    "severity": 5,
    "confidence": 1.0,
    "is_new_incident": true,
    "tool_calls_count": 5,
    "uncertainty_reason": null,
    "evidence_count": 1
  }
}
```

**2. Spans** (POST `/api/spans/ingest`):
- Sent only if trace_id was obtained AND spans list is non-empty
- Each span has: span_id, name, span_type (llm/tool), input_text, output_text, start_time, end_time, duration_ms, status, model

**Span names for process_report:**
`understand_report` → `retrieve_policy` → `generate_plan` → `search_incidents` (if existing) → `escalate_severity` (if escalated) → `correlate_incidents` (if correlated) → `create_incident` (if new) → `assign_team` → `dispatch_team` → `verify_outcome` → `generate_response`

**Span names for replan:**
`replan_assign_team` → `replan_dispatch` → `replan_generate_response`

### PRISM Configuration

```env
PRISMTRACE_HOST=https://prism-api-prod.up.railway.app
PRISMTRACE_PROJECT_ID=61b7b4c9-386d-492e-9b71-d4442ba08454
PRISMTRACE_API_KEY=pt-sk-77319815217044c9bbb2d102bad0d2ed
```

### Current PRISM Stats
- 133 traces captured
- Average satisfaction: 71.9/100
- 20 traces flagged for review
- All traces have evaluation scores

---

## 11. EVALUATION SCENARIOS (Complete)

| ID | Name | Reports | Expected | Checks |
|----|------|---------|----------|--------|
| E1 | Simple waste | 1 report about overflowing bins | category=waste, skill=waste_management, team assigned | 3 |
| E2 | Duplicates | 3 reports about same bins, ~2km apart | category=waste, correlation detected | 4 |
| E3 | Resource failure | Water leak + team_unavailable sim | category=water, replan executed | 3 |
| E4 | Accessibility | Blocked wheelchair ramp | category=accessibility | 2 |
| E5 | Road hazard | Fallen tree blocking road | category=road | 2 |
| E6 | Conflicting severity | Minor drip + EMERGENCY flood | severity 3-5 on second report | 3 |
| E7 | Incomplete evidence | "Something is wrong" | confidence < 0.5 | 1 |
| E8 | Conflicting category | Water puddle + road damage | Both processed | 1 |
| E9 | Multiple teams | Waste bin overflow | Team assigned | 1 |
| E10 | Resource disappears | Road hazard + team_unavailable | replan executed | 2 |
| E11 | High priority | Water main burst flooding | severity 4-5 | 1 |
| E12 | Replan quality | Water leak + team_unavailable | Response >50 chars, mentions next step | 3 |
| E13 | Noisy report | "Nice weather today!" | severity ≤ 2 | 1 |

**V1 Baseline:** 24/26 (92.3%)
**V2 Current:** 27/27 (100%)

---

## 12. DEMO SEQUENCE (For Judges)

### Flagship Demo: "Water Leak Response with Adaptive Replanning"

**Step 1: Submit Report**
```
Actor: Judge clicks "New Report" or types in chat
Input: "Water leak at Main and 3rd intersection, water gushing from pipe!"
Location: Downtown Core (40.7128, -74.006)
```

**Step 2: AXIOM Classifies**
```
PRISM trace appears: category=water, severity=5, confidence=1.0
Dashboard shows: New incident created, red severity badge
```

**Step 3: AXIOM Dispatches**
```
Available teams: Alpha Response, Bravo Services
Selected: Bravo Services (water + road capable, closest)
Assignment created, ETA: 1 min
Dashboard shows: Team assigned, incident status → "assigned"
```

**Step 4: Team Becomes Unavailable**
```
Actor: Demo controls → "Simulate: Team Unavailable"
Or: API call POST /api/simulate {"event_type": "team_unavailable", "parameters": {"team_category": "water"}}
Dashboard shows: Bravo Services status → "unavailable"
```

**Step 5: AXIOM Replans**
```
Actor: Demo controls → "Replan" or automatic
AXIOM detects stale plan
Searches for alternatives
Assigns Alpha Response (water capable)
Dashboard shows: "Replanned: Assigned Alpha Response"
PRISM trace: replan span with explanation
```

**Step 6: Show PRISM**
```
Open PRISM dashboard
Show trace: input → classify → plan → dispatch → replan → verify → respond
Show evaluation: satisfaction score
Show improvement: V1 (92.3%) → V2 (100%)
```

### Alternative Demo Scenarios

| Scenario | What It Shows |
|----------|---------------|
| `waste_overflow` | Duplicate detection, correlation |
| `vague_report` | Uncertainty handling, HOLD decision |
| `multi_incident` | Multiple concurrent incidents |
| `accessibility` | Domain-specific classification |
| `road_hazard` | Different domain, team selection |

---

## 13. ENVIRONMENT SETUP

### Required

```bash
# Python 3.11+
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# PostgreSQL 15
brew services start postgresql@15
createdb axiom

# Environment
cp .env.example .env
# Fill in: GROQ_API_KEY, PRISMTRACE_API_KEY
```

### .env Required Variables

```env
DATABASE_URL=postgresql+asyncpg://localhost:5432/axiom
DATABASE_URL_SYNC=postgresql://localhost:5432/axiom
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL_STRONG=qwen/qwen3.6-27b
GROQ_MODEL_FAST=allam-2-7b
GROQ_MODEL_VISION=qwen/qwen3.6-27b
PRISMTRACE_HOST=https://prism-api-prod.up.railway.app
PRISMTRACE_PROJECT_ID=61b7b4c9-386d-492e-9b71-d4442ba08454
PRISMTRACE_API_KEY=pt-sk-77319815217044c9bbb2d102bad0d2ed
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Run

```bash
PYTHONPATH=src uvicorn axiom.main:app --reload --port 8000
# Dashboard: http://localhost:8000/dashboard
# API docs: http://localhost:8000/docs
```

### Test

```bash
PYTHONPATH=src pytest tests/ -v
PYTHONPATH=src python -m axiom.evaluation.scenarios
```

---

## 14. KNOWN ISSUES TO FIX

### Span Lifecycle Bug (orchestrator.py:125-128)

The current code:
```python
prism.finish_span(
    spans[-1] if spans else prism.create_span("search_incidents", "tool", ...),
    span_understand_start,
) if spans else None
```

This is dead code. `spans` is always empty at this point. The span is created later (line 136) but its timing is wrong. Fix: Remove this block entirely. The `understand_report` span should start at `span_understand_start` and end after `_understand()` returns.

### Demo State Mutation (demo.py)

`run_full_demo()` modifies `scenario.steps[i]` in place when resolving `"dynamic"` incident IDs. On second run, the step already has the old ID. Fix: Deep-copy steps before modifying:
```python
import copy
steps = copy.deepcopy(scenario.steps)
```

### Frontend Status Filter (index.html)

The filter dropdown offers "open" but the actual IncidentStatus enum values are: `reported`, `acknowledged`, `assigned`, `dispatched`, `in_progress`, `resolved`, `failed`, `escalated`. Fix the dropdown options to match.

### Evaluation View Hardcoded (index.html)

The Evaluation tab shows hardcoded numbers. Fix: Create an API endpoint that returns evaluation summary, or fetch from PRISM API directly.

---

## 15. QUICK REFERENCE FOR ANTIGRAVITY

### Most Important Files (in order)

1. `src/axiom/api/orchestrator.py` — THE BRAIN. Read this first.
2. `frontend/index.html` — THE FACE. All UI lives here.
3. `src/axiom/tools/implementations/core_tools.py` — THE HANDS. All DB operations.
4. `src/axiom/main.py` — THE NERVES. All API routes.
5. `src/axiom/db/models/domain.py` — THE SKELETON. All data models.
6. `src/axiom/observability/prism.py` — THE EYES. PRISM tracing.
7. `src/axiom/evaluation/scenarios.py` — THE REPORT CARD. All tests.
8. `src/axiom/demo.py` — THE STAGE. Demo scenarios.
9. `src/axiom/world/seed.py` — THE CITY. Seed data.
10. `src/axiom/skills/registry.py` — THE PLAYBOOK. Domain knowledge.

### Quick Commands

```bash
# Start server
PYTHONPATH=src uvicorn axiom.main:app --reload

# Run evaluation
PYTHONPATH=src python -m axiom.evaluation.scenarios

# Run tests
PYTHONPATH=src pytest tests/ -v

# Submit report
curl -X POST http://localhost:8000/api/report \
  -H "Content-Type: application/json" \
  -d '{"text":"Water leak at Main and 3rd","latitude":40.7128,"longitude":-74.006}'

# Run demo
curl -X POST http://localhost:8000/api/demo/run/water_leak

# Get incidents
curl http://localhost:8000/api/incidents

# Get city state
curl http://localhost:8000/api/city-state
```

### What NOT to Break

- The orchestrator flow (process_report → PRISM trace)
- The evaluation suite (27/27 passing)
- The PRISM integration (traces + spans)
- The demo scenarios (especially water_leak)
- The weather integration (Open-Meteo, free, no key)

### What's Safe to Change

- Frontend (HTML/CSS/JS) — completely rewrite if needed
- City view (currently static cards — needs Canvas renderer)
- Evaluation view (currently hardcoded — make dynamic)
- Add new API endpoints
- Add new tools
- Improve LLM prompts
- Fix bugs listed in Section 14

---

**End of Blueprint. Antigravity: read this, then start building the 2D City Renderer and fixing the bugs in Section 14. The judges need to see a working map with pulsing incident markers.**
