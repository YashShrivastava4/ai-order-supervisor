"""SQLAlchemy models — supervisor_configs, runs, activity_log. See 01_MASTER_SPEC.md §4."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SupervisorConfig(Base):
    __tablename__ = "supervisor_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    base_instruction: Mapped[str] = mapped_column(Text)
    available_actions: Mapped[list] = mapped_column(JSONB)  # list of action names enabled
    # Next 3 fields are all optional per the PDF — app code (classifier §7,
    # run_agent_step §6) supplies the fallback when a template leaves them unset.
    default_wake_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wake_aggressiveness: Mapped[str | None] = mapped_column(String, nullable=True)  # 'conservative' | 'balanced' | 'aggressive'
    model_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # e.g. {"provider": "groq", "model": "..."}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    runs: Mapped[list["Run"]] = relationship(back_populates="supervisor_config")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supervisor_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supervisor_configs.id"), index=True
    )
    order_context: Mapped[dict] = mapped_column(JSONB)  # order id, customer, items, whatever the demo needs
    temporal_workflow_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'active' | 'asleep' | 'paused' | 'completed' | 'terminated' — a new run
    # starts 'active' since the workflow-start agent turn runs immediately (§5).
    status: Mapped[str] = mapped_column(String, default="active")
    sleep_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    memory_summary: Mapped[str] = mapped_column(Text, default="")
    final_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {summary, actions, learnings, feedback}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    supervisor_config: Mapped["SupervisorConfig"] = relationship(back_populates="runs")
    activity_log: Mapped[list["ActivityLog"]] = relationship(
        back_populates="run", order_by="ActivityLog.created_at"
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id"), index=True)
    # 'incoming_event' | 'wake_decision' | 'sleep_decision' | 'agent_action'
    # | 'manual_instruction' | 'lifecycle_event' | 'final_output'
    type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["Run"] = relationship(back_populates="activity_log")
