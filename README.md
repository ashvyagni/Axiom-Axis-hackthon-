# AXIOM — Adaptive AI City Operations Platform

> **AI for Smart Cities Track | ForgeAI Hackathon**

AXIOM is an AI operational supervisor that turns fragmented urban signals into coordinated, verifiable, and adaptive action. It is not a chatbot, ticketing wrapper, or dashboard with AI attached — it is a system where AI operates within a changing environment, makes decisions, acts through real tools, and verifies outcomes.

---

## Core Thesis

> **AXIOM is an AI system that observes what is happening, decides what should happen next, acts through operational tools, verifies the result, adapts to change, and continuously becomes more reliable through evaluation.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AXIOM ORCHESTRATOR                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  OBSERVE → UNDERSTAND → PRIORITIZE → PLAN → ACT → VERIFY   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ AI Layer │  │  Tools   │  │  Skills  │  │  World   │   │
│  │ (Groq)   │  │ (13 DB)  │  │  (7)     │  │  State   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                     PostgreSQL + PRISM                       │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Description |
|-----------|-------------|
| **Orchestrator** | Central agent loop: understand → classify → plan → act → verify → adapt |
| **AI Provider** | GroqCloud (qwen/qwen3.6-27b strong, allam-2-7b fast) |
| **13 Tools** | Database operations: search, create, correlate, dispatch, assign, policy, verify, simulate |
| **7 Skills** | Domain modules: waste, water, accessibility, road, dispatch, policy, verification |
| **World State** | PostgreSQL with 13 SQLAlchemy models: incidents, reports, teams, infrastructure, policies |
| **Weather** | Live Open-Meteo integration (free, no API key) for environment-aware decisions |
| **PRISM** | Observability: traces, spans, evaluation, improvement loop |

---

## Key Capabilities

### 1. Natural Language Understanding
Citizens submit reports in plain English. AXIOM classifies category, severity, and confidence.

```
Input: "Water leak at Main and 3rd intersection, water gushing from pipe!"
Output: {category: "water", severity: 5, confidence: 1.0}
```

### 2. Evidence-Based Uncertainty Detection
AXIOM does not manufacture certainty. Vague or incomplete reports trigger uncertainty handling.

```
Input: "Something is wrong on Main Street."
Output: {category: "road", severity: 3, confidence: 0.3, uncertainty_reason: "Report uses vague language"}
Decision: HOLD — insufficient confidence for dispatch
```

### 3. Duplicate Detection & Correlation
Multiple citizen reports about the same incident are correlated, not duplicated.

```
Report 1: "Water leak at Main and 3rd"
Report 2: "Same issue at intersection"
Result: Single incident, second report added as evidence
```

### 4. Adaptive Replanning
When conditions change (team unavailable, priority shift), AXIOM detects the invalid plan and replans.

```
Plan A: Assign Team B
Event: Team B becomes unavailable
AXIOM: Detects stale plan → searches alternatives → assigns Team C
```

### 5. Outcome Verification
AXIOM distinguishes ACTION COMPLETED from OUTCOME VERIFIED.

```
Action: Team dispatched
Verification: Check incident status
If failed: Trigger replan
If resolved: Close incident
```

### 6. Live Weather Integration
Real-time weather data from Open-Meteo influences severity assessment.

```
Weather: Heavy rain, wind 60km/h
Impact: Flooding risk → increase severity for water incidents
```

---

## The PRISM Improvement Loop

This is the core differentiator. We don't just build AI — we **measure and improve it**.

```
AXIOM V1
    ↓
Real Scenarios (13 evaluation scenarios)
    ↓
PRISM (traces, spans, evaluation scores)
    ↓
Failure Pattern (replan traces scored 35-45 satisfaction)
    ↓
Root Cause (hallucinated details, no concrete next steps)
    ↓
Engineering Change (prompt improvement, deterministic planning)
    ↓
AXIOM V2
    ↓
Same Scenarios
    ↓
PRISM
    ↓
Measured Improvement (92.3% → 100%)
```

### PRISM Integration Details

**Every AXIOM run captures:**

| Span | Type | What It Tracks |
|------|------|----------------|
| `understand_report` | LLM | AI classification of citizen report |
| `generate_plan` | Deterministic | Priority, risk factors, expected outcome |
| `search_incidents` | Tool | Finding similar incidents in area |
| `create_incident` | Tool | Creating new incident record |
| `escalate_severity` | Tool | Evidence-based severity update |
| `correlate_incidents` | Tool | Linking related incidents |
| `dispatch_team` | Tool | Team availability lookup |
| `assign_team` | Tool | Resource assignment |
| `retrieve_policy` | Tool | Knowledge/policy lookup |
| `verify_outcome` | Tool | Post-action verification |
| `generate_response` | LLM | Natural language response to operator |

**PRISM evaluates:**
- Customer satisfaction (0-100)
- Intent detection accuracy
- Response quality
- Flag for review when thresholds exceeded

**Results:**
- 133 traces captured
- Average satisfaction: 71.9/100
- 20 traces flagged for improvement
- V1 → V2 improvement: +7.7 percentage points

---

## Evaluation Scenarios

| ID | Scenario | What It Tests |
|----|----------|---------------|
| E1 | Simple waste incident | Basic classification and dispatch |
| E2 | Duplicate reports | Correlation detection |
| E3 | Resource failure + replan | Adaptive replanning |
| E4 | Accessibility obstruction | Domain-specific classification |
| E5 | Road hazard | Domain-specific classification |
| E6 | Conflicting severity reports | Evidence reconciliation |
| E7 | Incomplete evidence | Uncertainty detection |
| E8 | Conflicting category reports | Category mismatch handling |
| E9 | Multiple teams | Resource selection |
| E10 | Resource disappears mid-assignment | Replanning recovery |
| E11 | High-priority interrupt | Priority handling |
| E12 | Replan quality check | Response quality |
| E13 | Noisy/irrelevant report | False signal rejection |

**V1 Baseline:** 24/26 (92.3%)
**V2 Improved:** 27/27 (100%)
**Improvement:** +7.7 percentage points

---

## Dashboard

The operational dashboard provides:

- **Overview**: Active incidents, critical count, available teams, recent activity
- **Incidents**: Filterable list with category, severity, status
- **Resources**: Team availability, capabilities, ETAs
- **AXIOM Activity**: Operational timeline of AI decisions
- **City View**: Districts and infrastructure status
- **Evaluation**: PRISM scores and metrics

Access at: `http://localhost:8000/dashboard`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/report` | Submit citizen report |
| `GET` | `/api/incidents` | List incidents |
| `GET` | `/api/incidents/{id}` | Get incident detail |
| `GET` | `/api/teams` | List available teams |
| `GET` | `/api/city-state` | Get city state |
| `POST` | `/api/simulate` | Trigger simulation event |
| `POST` | `/api/replan/{id}` | Replan for incident |
| `GET` | `/api/runs` | List AXIOM runs |
| `GET` | `/api/weather` | Get weather data |
| `GET` | `/api/demo/scenarios` | List demo scenarios |
| `POST` | `/api/demo/run/{name}` | Run demo scenario |

---

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 15
- GroqCloud API key (free tier)

### Installation

```bash
# Clone
git clone https://github.com/ashvyagni/Axiom-Axis-hackthon-.git
cd Axiom-Axis-hackthon-

# Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Database
brew services start postgresql@15
createdb axiom

# Environment
cp .env.example .env
# Edit .env with your keys

# Run
PYTHONPATH=src uvicorn axiom.main:app --reload
```

### Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://localhost:5432/axiom
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL_STRONG=qwen/qwen3.6-27b
GROQ_MODEL_FAST=allam-2-7b
PRISMTRACE_HOST=https://prism-api-prod.up.railway.app
PRISMTRACE_PROJECT_ID=your-project-id
PRISMTRACE_API_KEY=pt-sk-your-key
```

### Run Tests

```bash
PYTHONPATH=src pytest tests/ -v
PYTHONPATH=src python -m axiom.evaluation.scenarios
```

---

## Demo

### Quick Start

```bash
# Submit a report
curl -X POST http://localhost:8000/api/report \
  -H "Content-Type: application/json" \
  -d '{"text": "Water leak at Main and 3rd intersection", "latitude": 40.7128, "longitude": -74.006}'

# Run a demo scenario
curl -X POST http://localhost:8000/api/demo/run/water_leak
```

### Demo Scenarios

| Scenario | Description |
|----------|-------------|
| `water_leak` | Full loop: report → classify → dispatch → team unavailable → replan |
| `waste_overflow` | Multiple reports → correlation → dispatch |
| `accessibility` | Blocked ramp → accessibility skill → dispatch |
| `road_hazard` | Fallen tree → road incident → dispatch |
| `vague_report` | Uncertain report → hold dispatch → verification |
| `multi_incident` | Multiple incidents → resource management |

---

## Tech Stack

- **Backend**: Python 3.14, FastAPI, SQLAlchemy (async)
- **Database**: PostgreSQL 15
- **AI**: GroqCloud (qwen/qwen3.6-27b, allam-2-7b)
- **Frontend**: HTML/CSS/JS, Tailwind CSS
- **Observability**: PRISM (traces, spans, evaluation)
- **Live Data**: Open-Meteo Weather API (free)

---

## Project Structure

```
AxiomAI/
├── frontend/
│   └── index.html              # Operational dashboard
├── src/axiom/
│   ├── ai/
│   │   ├── base.py             # AI provider ABC
│   │   └── groq.py             # GroqCloud implementation
│   ├── api/
│   │   └── orchestrator.py     # Core agent loop
│   ├── db/
│   │   ├── engine.py           # SQLAlchemy async engine
│   │   └── models/
│   │       └── domain.py       # 13 domain models
│   ├── evaluation/
│   │   └── scenarios.py        # 13 evaluation scenarios
│   ├── observability/
│   │   └── prism.py            # PRISM adapter with spans
│   ├── skills/
│   │   └── registry.py         # 7 domain skills
│   ├── tools/
│   │   └── implementations/
│   │       └── core_tools.py   # 13 typed tools
│   ├── world/
│   │   ├── seed.py             # City seed data
│   │   └── weather.py          # Live weather provider
│   ├── demo.py                 # Demo scenarios
│   ├── config.py               # Pydantic settings
│   └── main.py                 # FastAPI app
├── tests/
│   ├── test_core.py
│   └── test_tools.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## How We Used PRISM

1. **Traces**: Every AXIOM run sends a trace to PRISM with input, output, model, latency, and metadata
2. **Spans**: Each operation (understand, search, create, dispatch, assign, policy, verify, respond) is captured as a span with timing
3. **Evaluation**: PRISM evaluates satisfaction and quality, flagging traces below thresholds
4. **Diagnosis**: We analyzed PRISM traces to identify weak replan responses (35-45 satisfaction)
5. **Improvement**: Based on PRISM findings, we improved prompts and added deterministic planning
6. **Measurement**: V1 → V2 improvement measured: 92.3% → 100% (+7.7pp)

---

## What Makes This Different

| Aspect | Typical Smart City | AXIOM |
|--------|-------------------|-------|
| AI Role | Classification only | Full operational loop |
| Tools | Mock/hardcoded | Real database operations |
| Verification | None | Outcome verification |
| Replanning | None | Adaptive when conditions change |
| Evaluation | None | PRISM + reproducible scenarios |
| Improvement | Static | Measured V1 → V2 improvement |
| Uncertainty | Overconfident | Detects and handles uncertainty |

---

## License

MIT

---

## Team

Built at ForgeAI Hackathon 2026
