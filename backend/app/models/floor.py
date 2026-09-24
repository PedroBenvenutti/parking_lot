from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Floor(Base):
    __tablename__ = "floors"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    capacity: Mapped[int] = mapped_column(Integer)
    # Ordem no prédio (1 = primeiro andar).
    position: Mapped[int] = mapped_column(Integer, unique=True)

    owner: Mapped["User"] = relationship(back_populates="floor")  # noqa: F821
    spots: Mapped[list["Spot"]] = relationship(
        back_populates="floor", order_by="Spot.position", cascade="all, delete-orphan"
    )


class Spot(Base):
    """Vaga. Gerada a partir da capacidade do andar, organizada em fileiras."""

    __tablename__ = "spots"
    __table_args__ = (
        UniqueConstraint("floor_id", "position"),
        UniqueConstraint("floor_id", "row", "column"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    row: Mapped[int] = mapped_column(Integer)
    column: Mapped[int] = mapped_column(Integer)

    floor: Mapped[Floor] = relationship(back_populates="spots")
