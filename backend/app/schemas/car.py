from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import CarStatus, Effort, EventType, Priority


class TaskTypeOut(BaseModel):
    id: int
    name: str
    icon: str


class TaskTypeCreate(BaseModel):
    name: str
    icon: str


class ClockOut(BaseModel):
    is_overdue: bool
    is_stale: bool
    stopped_seconds: int
    stale_limit_seconds: int
    last_movement_at: datetime | None
    computed_at: datetime


class CarOut(BaseModel):
    id: int
    plate: str
    title: str
    description: str
    task_type: TaskTypeOut
    effort: Effort
    priority: Priority
    due_at: datetime
    status: CarStatus
    hazard_on: bool
    floor_id: int | None
    spot_ids: list[int]
    spot_positions: list[int]
    created_by: int
    created_at: datetime
    clock: ClockOut


class CarCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    task_type_id: int
    effort: Effort
    priority: Priority
    due_at: datetime


class CarUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    task_type_id: int | None = None
    effort: Effort | None = None
    priority: Priority | None = None
    due_at: datetime | None = None


class ParkIn(BaseModel):
    floor_id: int
    spot_id: int


class MoveIn(BaseModel):
    spot_id: int


class HazardIn(BaseModel):
    on: bool


class ReturnIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ActorOut(BaseModel):
    id: int
    name: str


class EventOut(BaseModel):
    id: int
    type: EventType
    actor: ActorOut
    timestamp: datetime
    payload: dict[str, Any]
