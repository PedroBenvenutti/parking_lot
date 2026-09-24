from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Sequence,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import CarStatus, Effort, EventType, Priority

plate_seq = Sequence("car_plate_seq")


def _enum(enum_cls: type) -> Enum:
    # native_enum=False: vira VARCHAR + CHECK, mais simples de migrar que enum nativo do Postgres.
    return Enum(enum_cls, native_enum=False, values_callable=lambda e: [m.value for m in e], length=20)


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    task_type_id: Mapped[int] = mapped_column(ForeignKey("task_types.id"))
    effort: Mapped[Effort] = mapped_column(_enum(Effort))
    priority: Mapped[Priority] = mapped_column(_enum(Priority))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[CarStatus] = mapped_column(_enum(CarStatus), default=CarStatus.PATIO)
    hazard_on: Mapped[bool] = mapped_column(Boolean, default=False)
    # Nulo no pátio. Após concluir, guarda o último andar (para o histórico).
    floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    task_type: Mapped["TaskType"] = relationship(lazy="joined")  # noqa: F821
    creator: Mapped["User"] = relationship()  # noqa: F821
    car_spots: Mapped[list["CarSpot"]] = relationship(
        back_populates="car", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="car", order_by="Event.timestamp, Event.id"
    )

    @property
    def spots(self) -> list["Spot"]:  # noqa: F821
        return sorted((cs.spot for cs in self.car_spots), key=lambda s: s.position)


class CarSpot(Base):
    """Carro ↔ vagas. spot_id é único: uma vaga comporta um veículo só."""

    __tablename__ = "car_spots"

    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id", ondelete="CASCADE"), primary_key=True)
    spot_id: Mapped[int] = mapped_column(
        ForeignKey("spots.id", ondelete="RESTRICT"), primary_key=True, unique=True
    )

    car: Mapped[Car] = relationship(back_populates="car_spots")
    spot: Mapped["Spot"] = relationship(lazy="joined")  # noqa: F821


class Event(Base):
    """Log imutável (UPDATE/DELETE bloqueados por trigger no banco)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"), index=True)
    type: Mapped[EventType] = mapped_column(_enum(EventType))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    car: Mapped[Car] = relationship(back_populates="events")
    actor: Mapped["User"] = relationship(lazy="joined")  # noqa: F821
