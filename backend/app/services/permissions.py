"""Regras de permissão (seção 3 da SPEC).

Tudo aqui opera sobre um `Principal`, um retrato imutável do usuário e seus papéis.
As mesmas funções são usadas pela API REST e pelo WebSocket.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Car, CarStatus, Floor, User, ValetAssignment
from app.services.errors import Forbidden, NotFound, Unauthorized


@dataclass(frozen=True)
class Principal:
    user_id: int
    name: str
    is_manager: bool
    is_valet: bool
    owned_floor_id: int | None
    valet_type_ids: frozenset[int]


def load_principal(db: Session, user_id: int) -> Principal:
    user = db.get(User, user_id)
    if user is None:
        raise Unauthorized("Usuário não encontrado")
    floor_id = db.scalar(select(Floor.id).where(Floor.owner_id == user_id))
    type_ids = db.scalars(select(ValetAssignment.task_type_id).where(ValetAssignment.user_id == user_id)).all()
    return Principal(
        user_id=user.id,
        name=user.name,
        is_manager=user.is_manager,
        is_valet=user.is_valet,
        owned_floor_id=floor_id,
        valet_type_ids=frozenset(type_ids),
    )


# --- visualização -------------------------------------------------------------


def can_view_patio(p: Principal) -> bool:
    return p.is_manager or p.is_valet


def can_view_patio_car(p: Principal, task_type_id: int) -> bool:
    return p.is_manager or (p.is_valet and task_type_id in p.valet_type_ids)


def can_view_all_floors(p: Principal) -> bool:
    return p.is_manager or p.is_valet


def can_view_floor(p: Principal, floor_id: int) -> bool:
    return can_view_all_floors(p) or p.owned_floor_id == floor_id


def can_view_car(p: Principal, car: Car) -> bool:
    if car.status == CarStatus.PATIO:
        return can_view_patio_car(p, car.task_type_id)
    return car.floor_id is not None and can_view_floor(p, car.floor_id)


# --- ações --------------------------------------------------------------------


def can_park(p: Principal, task_type_id: int) -> bool:
    return p.is_manager or (p.is_valet and task_type_id in p.valet_type_ids)


def is_floor_owner(p: Principal, floor_id: int | None) -> bool:
    return floor_id is not None and p.owned_floor_id == floor_id


def can_return_to_patio(p: Principal, car: Car) -> bool:
    return p.is_manager or is_floor_owner(p, car.floor_id)


# --- guardas (levantam erro) --------------------------------------------------


def ensure_can_view_floor(p: Principal, floor_id: int) -> None:
    if not can_view_floor(p, floor_id):
        raise Forbidden("Você não tem acesso a este andar")


def ensure_can_view_patio(p: Principal) -> None:
    if not can_view_patio(p):
        raise Forbidden("Você não tem acesso ao pátio")


def ensure_can_view_car(p: Principal, car: Car) -> None:
    # 404 em vez de 403 para não revelar a existência de carros de outros andares.
    if not can_view_car(p, car):
        raise NotFound("Veículo não encontrado")


def ensure_floor_owner(p: Principal, car: Car) -> None:
    if not is_floor_owner(p, car.floor_id):
        raise Forbidden("Apenas o dono do andar pode fazer isso")


def ensure_manager(p: Principal) -> None:
    if not p.is_manager:
        raise Forbidden("Apenas o gestor pode fazer isso")
