import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from axiom.db.engine import Base
import enum


class IncidentCategory(str, enum.Enum):
    WASTE = "waste"
    WATER = "water"
    ACCESSIBILITY = "accessibility"
    ROAD = "road"


class IncidentStatus(str, enum.Enum):
    REPORTED = "reported"
    ACKNOWLEDGED = "acknowledged"
    ASSIGNED = "assigned"
    DISPATCHED = "dispatched"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    FAILED = "failed"
    ESCALATED = "escalated"


class TeamStatus(str, enum.Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    DISPATCHED = "dispatched"
    UNAVAILABLE = "unavailable"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default=IncidentStatus.REPORTED.value)
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    district_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    reports: Mapped[list["Report"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    evidence: Mapped[list["IncidentEvidence"]] = relationship(back_populates="incident", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    text: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    source_type: Mapped[str] = mapped_column(String(50), default="citizen")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incident: Mapped["Incident"] = relationship(back_populates="reports")


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    evidence_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(100), default="report")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incident: Mapped["Incident"] = relationship(back_populates="evidence")


class IncidentRelation(Base):
    __tablename__ = "incident_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_a_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    incident_b_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    relation_type: Mapped[str] = mapped_column(String(50), default="related")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class District(Base):
    __tablename__ = "districts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    population: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=1)


class Infrastructure(Base):
    __tablename__ = "infrastructure"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(50))
    district_id: Mapped[str] = mapped_column(String(36), ForeignKey("districts.id"))
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="operational")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default=TeamStatus.AVAILABLE.value)
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)
    current_assignment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    capabilities: Mapped[list["TeamCapability"]] = relationship(back_populates="team", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class TeamCapability(Base):
    __tablename__ = "team_capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id"))
    category: Mapped[str] = mapped_column(String(50))
    proficiency: Mapped[int] = mapped_column(Integer, default=1)

    team: Mapped["Team"] = relationship(back_populates="capabilities")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id"))
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    status: Mapped[str] = mapped_column(String(50), default="assigned")
    eta_minutes: Mapped[int] = mapped_column(Integer, default=0)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    team: Mapped["Team"] = relationship(back_populates="assignments")
    incident: Mapped["Incident"] = relationship(back_populates="assignments")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    relevant_categories: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("incidents.id"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="running")
    skill_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id"))
    tool_name: Mapped[str] = mapped_column(String(100))
    input_json: Mapped[dict] = mapped_column(JSON)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    expected_outcome: Mapped[str] = mapped_column(Text)
    observed_outcome: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorldStateChange(Base):
    __tablename__ = "world_state_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    field: Mapped[str] = mapped_column(String(100))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    cause: Mapped[str] = mapped_column(String(100), default="agent_action")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    config_json: Mapped[dict] = mapped_column(JSON)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
