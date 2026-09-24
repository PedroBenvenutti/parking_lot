import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

# Aponta a aplicação para o banco de testes ANTES de importar qualquer módulo do app.
from app.config import get_settings

os.environ["DATABASE_URL"] = get_settings().test_database_url
os.environ["CLOCK_TICK_SECONDS"] = "0"
get_settings.cache_clear()

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import Effort, Priority, TaskType, User  # noqa: E402
from app.services import cars as car_service  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.floors import create_floor  # noqa: E402
from app.services.permissions import Principal, load_principal  # noqa: E402

PASSWORD = "senha123"
# Hash calculado uma vez só: PBKDF2 é propositalmente lento.
PASSWORD_HASH = hash_password(PASSWORD)
# Segunda-feira, 21/09/2026, 10:00 em São Paulo (13:00 UTC).
MONDAY = datetime(2026, 9, 21, 13, 0, tzinfo=UTC)


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().test_database_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_db() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE events, car_spots, cars, spots, floors, valet_assignments, users, task_types "
                "RESTART IDENTITY CASCADE"
            )
        )
        conn.execute(text("ALTER SEQUENCE car_plate_seq RESTART"))


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    counter = iter(range(1, 10_000))

    def _make(
        name: str | None = None,
        *,
        is_manager: bool = False,
        is_valet: bool = False,
        valet_types: list[TaskType] | None = None,
        floor_capacity: int | None = None,
    ) -> User:
        n = next(counter)
        user = User(
            name=name or f"Pessoa {n}",
            email=f"pessoa{n}@exemplo.com",
            password_hash=PASSWORD_HASH,
            is_manager=is_manager,
            is_valet=is_valet,
        )
        user.valet_types = valet_types or []
        db.add(user)
        db.flush()
        if floor_capacity is not None:
            create_floor(db, user, floor_capacity)
        db.commit()
        return user

    return _make


@pytest.fixture
def make_type(db: Session) -> Callable[..., TaskType]:
    def _make(name: str = "Pedido", icon: str = "📦") -> TaskType:
        task_type = TaskType(name=name, icon=icon)
        db.add(task_type)
        db.commit()
        return task_type

    return _make


@pytest.fixture
def principal(db: Session) -> Callable[[User], Principal]:
    return lambda user: load_principal(db, user.id)


@pytest.fixture
def make_car(db: Session, principal: Callable[[User], Principal]) -> Callable[..., int]:
    def _make(
        creator: User,
        task_type: TaskType,
        *,
        effort: Effort = Effort.CARRO,
        priority: Priority = Priority.MEDIA,
        due_at: datetime | None = None,
        now: datetime = MONDAY,
    ) -> int:
        change = car_service.create_car(
            db,
            principal(creator),
            title="Tarefa",
            description="",
            task_type_id=task_type.id,
            effort=effort,
            priority=priority,
            due_at=due_at or now + timedelta(days=7),
            now=now,
        )
        db.commit()
        return change.car.id

    return _make
