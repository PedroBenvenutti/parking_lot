from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Papéis acumuláveis. "Dono de andar" é derivado de existir um Floor com owner_id = user.id.
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    is_valet: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    floor: Mapped["Floor | None"] = relationship(back_populates="owner", uselist=False)  # noqa: F821
    valet_types: Mapped[list["TaskType"]] = relationship(  # noqa: F821
        secondary="valet_assignments", order_by="TaskType.name"
    )


class ValetAssignment(Base):
    """Manobrista ↔ tipos de tarefa sob sua responsabilidade."""

    __tablename__ = "valet_assignments"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    task_type_id: Mapped[int] = mapped_column(ForeignKey("task_types.id", ondelete="CASCADE"), primary_key=True)
