"""Pydantic schemas mirroring app/db/models.py (spec §4).

Only SupervisorConfig schemas are filled in for S3 — Run and ActivityLog
schemas are stubbed below and get built in S8, per the master spec's build
order. Keeping the stubs visible now, same convention used for the empty
module placeholders from S1.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupervisorConfigBase(BaseModel):
    name: str
    base_instruction: str
    available_actions: list[str]
    default_wake_seconds: int | None = None
    wake_aggressiveness: str | None = None
    # The SQLAlchemy column is literally named `model_config` (spec §4), but
    # Pydantic v2 reserves that name on BaseModel for its own ConfigDict —
    # aliasing it to a differently-named field is the fix flagged in
    # 02_PROGRESS.md (session 4). populate_by_name below lets callers use
    # either the alias or this field name when constructing one in Python.
    model_cfg: dict | None = Field(default=None, alias="model_config")

    model_config = ConfigDict(populate_by_name=True)


class SupervisorConfigCreate(SupervisorConfigBase):
    pass


class SupervisorConfigResponse(SupervisorConfigBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# TODO(S8): RunCreate / RunResponse — mirrors `runs` table, needed once
# POST /api/runs and GET /api/runs/{id} exist.

# TODO(S8): ActivityLogResponse — mirrors `activity_log` table, needed for
# the run-detail timeline endpoint.
