from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/order_supervisor"


class Base(DeclarativeBase):
    pass


class Supervisor(Base):
    __tablename__ = "supervisors"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    available_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    default_wakeup_behavior: Mapped[str] = mapped_column(Text, nullable=True)
    model_config: Mapped[str] = mapped_column(Text, nullable=True)
    wakeup_aggressiveness: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    supervisor_id: Mapped[str] = mapped_column(
        ForeignKey("supervisors.id"), nullable=False
    )
    order_id: Mapped[str] = mapped_column(String, nullable=False)
    order_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    memory_summary: Mapped[str] = mapped_column(Text, nullable=True)
    wakeup_guidance: Mapped[str] = mapped_column(JSON, nullable=True)
    next_wakeup_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    final_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    supervisor: Mapped[Supervisor] = relationship()


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
