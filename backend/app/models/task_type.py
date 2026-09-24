from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TaskType(Base):
    __tablename__ = "task_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    # Emoji exibido no teto do veículo.
    icon: Mapped[str] = mapped_column(String(16))
