from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaskType, User
from app.services.auth import hash_password
from app.services.errors import Conflict, InvalidInput, NotFound
from app.services.floors import create_floor
from app.services.permissions import Principal, ensure_manager


def list_users(db: Session, p: Principal) -> list[User]:
    ensure_manager(p)
    return list(db.scalars(select(User).order_by(User.name)))


def _task_types(db: Session, ids: list[int]) -> list[TaskType]:
    types = list(db.scalars(select(TaskType).where(TaskType.id.in_(ids))))
    if len(types) != len(set(ids)):
        raise InvalidInput("Tipo de tarefa inválido")
    return types


def create_user(
    db: Session,
    p: Principal,
    *,
    name: str,
    email: str,
    password: str,
    is_manager: bool = False,
    is_valet: bool = False,
    valet_type_ids: list[int] | None = None,
    floor_capacity: int | None = None,
) -> User:
    ensure_manager(p)
    email = email.strip().lower()
    if not name.strip() or not email or len(password) < 6:
        raise InvalidInput("Informe nome, e-mail e uma senha com pelo menos 6 caracteres")
    if db.scalar(select(User.id).where(User.email == email)):
        raise Conflict("Já existe um usuário com este e-mail")
    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        is_manager=is_manager,
        is_valet=is_valet,
    )
    user.valet_types = _task_types(db, valet_type_ids or [])
    db.add(user)
    db.flush()
    if floor_capacity is not None:
        create_floor(db, user, floor_capacity)
    return user


def update_roles(
    db: Session,
    p: Principal,
    user_id: int,
    *,
    is_manager: bool | None = None,
    is_valet: bool | None = None,
    valet_type_ids: list[int] | None = None,
) -> User:
    """Gestor configura papéis e os tipos sob responsabilidade de cada manobrista."""
    ensure_manager(p)
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("Usuário não encontrado")
    if is_manager is not None:
        if user.id == p.user_id and not is_manager:
            raise Conflict("Você não pode remover o seu próprio papel de gestor")
        user.is_manager = is_manager
    if is_valet is not None:
        user.is_valet = is_valet
    if valet_type_ids is not None:
        user.valet_types = _task_types(db, valet_type_ids)
    db.flush()
    return user


def list_task_types(db: Session) -> list[TaskType]:
    return list(db.scalars(select(TaskType).order_by(TaskType.name)))


def create_task_type(db: Session, p: Principal, name: str, icon: str) -> TaskType:
    ensure_manager(p)
    if not name.strip() or not icon.strip():
        raise InvalidInput("Informe nome e ícone")
    if db.scalar(select(TaskType.id).where(TaskType.name == name.strip())):
        raise Conflict("Já existe um tipo com este nome")
    task_type = TaskType(name=name.strip(), icon=icon.strip())
    db.add(task_type)
    db.flush()
    return task_type
