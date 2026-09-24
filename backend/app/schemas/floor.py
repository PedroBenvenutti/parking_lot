from pydantic import BaseModel, Field

from app.schemas.car import CarOut


class OwnerOut(BaseModel):
    id: int
    name: str


class SpotOut(BaseModel):
    id: int
    position: int
    row: int
    column: int


class FloorSummary(BaseModel):
    id: int
    position: int
    capacity: int
    occupied: int
    owner: OwnerOut


class FloorDetail(FloorSummary):
    spots: list[SpotOut]
    cars: list[CarOut]


class FloorCapacityIn(BaseModel):
    capacity: int = Field(ge=1, le=60)
