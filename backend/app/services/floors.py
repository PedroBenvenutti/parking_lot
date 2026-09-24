from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CarSpot, Floor, Spot, User
from app.services.errors import Conflict, InvalidInput, NotFound
from app.services.permissions import Principal, can_view_all_floors, ensure_manager


def get_floor(db: Session, floor_id: int, *, lock: bool = False) -> Floor:
    stmt = select(Floor).where(Floor.id == floor_id)
    if lock:
        stmt = stmt.with_for_update()
    floor = db.scalar(stmt)
    if floor is None:
        raise NotFound("Andar não encontrado")
    return floor


def visible_floors(db: Session, p: Principal) -> list[Floor]:
    stmt = select(Floor).order_by(Floor.position)
    if not can_view_all_floors(p):
        if p.owned_floor_id is None:
            return []
        stmt = stmt.where(Floor.id == p.owned_floor_id)
    return list(db.scalars(stmt))


def occupied_counts(db: Session, floor_ids: list[int]) -> dict[int, int]:
    rows = db.execute(
        select(Spot.floor_id, func.count(CarSpot.spot_id))
        .join(CarSpot, CarSpot.spot_id == Spot.id)
        .where(Spot.floor_id.in_(floor_ids))
        .group_by(Spot.floor_id)
    )
    return {floor_id: count for floor_id, count in rows}


def occupied_spot_ids(db: Session, floor_id: int) -> set[int]:
    return set(
        db.scalars(select(CarSpot.spot_id).join(Spot, Spot.id == CarSpot.spot_id).where(Spot.floor_id == floor_id))
    )


def sync_spots(db: Session, floor: Floor) -> None:
    """Gera/remove vagas para que o andar tenha exatamente `capacity` vagas."""
    per_row = get_settings().spots_per_row
    existing = {spot.position: spot for spot in floor.spots}
    for position in range(floor.capacity):
        if position not in existing:
            floor.spots.append(Spot(position=position, row=position // per_row, column=position % per_row))
    to_remove = [spot for pos, spot in existing.items() if pos >= floor.capacity]
    if to_remove:
        occupied = occupied_spot_ids(db, floor.id)
        if any(spot.id in occupied for spot in to_remove):
            raise Conflict("Há veículos nas vagas que seriam removidas. Libere-as antes de reduzir.")
        for spot in to_remove:
            floor.spots.remove(spot)
    db.flush()


def create_floor(db: Session, owner: User, capacity: int) -> Floor:
    if capacity < 1:
        raise InvalidInput("O andar precisa de pelo menos 1 vaga")
    last_position = db.scalar(select(func.max(Floor.position))) or 0
    floor = Floor(owner=owner, capacity=capacity, position=last_position + 1)
    db.add(floor)
    db.flush()
    sync_spots(db, floor)
    return floor


def set_capacity(db: Session, p: Principal, floor_id: int, capacity: int) -> Floor:
    ensure_manager(p)
    if capacity < 1:
        raise InvalidInput("O andar precisa de pelo menos 1 vaga")
    floor = get_floor(db, floor_id, lock=True)
    floor.capacity = capacity
    sync_spots(db, floor)
    return floor
