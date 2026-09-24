"""Popula o banco com dados de demonstração (seção 12 da SPEC).

Apaga TODOS os dados antes. Uso: python seed.py
Senha de todos os usuários: senha123
"""

import random
import unicodedata
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import CarSpot, Effort, Floor, Priority, Spot, TaskType, User
from app.services import cars as car_service
from app.services.auth import hash_password
from app.services.floors import create_floor
from app.services.permissions import load_principal

PASSWORD = "senha123"

TASK_TYPES = [
    ("Pedido", "📦"),
    ("Nota fiscal", "🧾"),
    ("Cadastro de cliente", "👤"),
    ("Devolução", "↩️"),
    ("Cotação", "💲"),
    ("Contrato", "📄"),
]

# (nome, capacidade do andar)
OWNERS = [
    ("Ana Souza", 6),
    ("Bruno Lima", 8),
    ("Carla Mendes", 10),
    ("Diego Rocha", 4),
    ("Elisa Martins", 12),
    ("Felipe Costa", 6),
    ("Gabriela Alves", 9),
    ("Henrique Dias", 14),
    ("Isabela Nunes", 5),
    ("João Pereira", 8),
    ("Karina Ribeiro", 11),
    ("Lucas Ferreira", 7),
]

TITLES = [
    "Liberar pedido bloqueado por crédito",
    "Corrigir CFOP da nota",
    "Cadastrar novo cliente do distribuidor",
    "Analisar devolução parcial",
    "Enviar cotação de reposição",
    "Revisar cláusula de reajuste",
    "Conferir divergência de preço",
    "Atualizar limite de crédito",
    "Cancelar pedido duplicado",
    "Emitir carta de correção",
    "Ajustar condição de pagamento",
    "Validar documentação fiscal",
]


def email_for(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    first, last = ascii_name.lower().split()[:2]
    return f"{first}.{last}@exemplo.com"


def reset(db: Session) -> None:
    db.execute(
        text(
            "TRUNCATE events, car_spots, cars, spots, floors, valet_assignments, users, task_types "
            "RESTART IDENTITY CASCADE"
        )
    )
    db.execute(text("ALTER SEQUENCE car_plate_seq RESTART"))
    db.commit()


def free_start_spot(db: Session, floor: Floor, effort: Effort, rng: random.Random) -> Spot | None:
    """Escolhe uma vaga livre (para caminhão, uma com a vizinha da direita livre)."""
    taken = set(db.scalars(select(CarSpot.spot_id)))
    by_rc = {(s.row, s.column): s for s in floor.spots}
    candidates = []
    for spot in floor.spots:
        if spot.id in taken:
            continue
        if effort == Effort.CAMINHAO:
            neighbor = by_rc.get((spot.row, spot.column + 1))
            if neighbor is None or neighbor.id in taken:
                continue
        candidates.append(spot)
    return rng.choice(candidates) if candidates else None


def main() -> None:
    rng = random.Random(42)
    now = datetime.now(UTC)
    db = SessionLocal()
    reset(db)
    password_hash = hash_password(PASSWORD)

    types = [TaskType(name=name, icon=icon) for name, icon in TASK_TYPES]
    db.add_all(types)
    db.flush()

    manager = User(name="Gestora Vendas", email="gestora@exemplo.com", password_hash=password_hash, is_manager=True)
    db.add(manager)
    db.flush()

    owners: list[User] = []
    for name, capacity in OWNERS:
        user = User(name=name, email=email_for(name), password_hash=password_hash)
        db.add(user)
        db.flush()
        create_floor(db, user, capacity)
        owners.append(user)

    # Um manobrista dedicado e uma dona de andar que também é manobrista.
    valet = User(name="Marcos Manobrista", email="marcos@exemplo.com", password_hash=password_hash, is_valet=True)
    valet.valet_types = types[:3]
    db.add(valet)
    owners[0].is_valet = True
    owners[0].valet_types = types[3:]
    db.commit()

    manager_p = load_principal(db, manager.id)

    def new_car(created_at: datetime, due_at: datetime, effort: Effort | None = None) -> int:
        creator = rng.choice(owners + [valet])
        change = car_service.create_car(
            db,
            load_principal(db, creator.id),
            title=rng.choice(TITLES),
            description="Tarefa de demonstração gerada pelo seed.",
            task_type_id=rng.choice(types).id,
            effort=effort or rng.choice(list(Effort)),
            priority=rng.choice(list(Priority)),
            due_at=due_at,
            now=created_at,
        )
        return change.car.id

    efforts_cycle = list(Effort)
    for index, owner in enumerate(owners):
        floor = db.scalar(select(Floor).where(Floor.owner_id == owner.id))
        owner_p = load_principal(db, owner.id)
        target = max(1, int(floor.capacity * rng.uniform(0.4, 0.75)))
        for n in range(target):
            # Estacionado entre 0 e 8 dias atrás: os mais antigos ficam "parados".
            parked_at = now - timedelta(days=rng.uniform(0, 8))
            created_at = parked_at - timedelta(hours=rng.uniform(1, 30))
            overdue = rng.random() < 0.25
            due_at = now - timedelta(days=rng.uniform(0.5, 3)) if overdue else now + timedelta(days=rng.uniform(1, 10))
            effort = efforts_cycle[(index + n) % 3]  # garante todos os tamanhos
            spot = free_start_spot(db, floor, effort, rng)
            if spot is None:
                effort = Effort.MOTO
                spot = free_start_spot(db, floor, effort, rng)
                if spot is None:
                    break
            car_id = new_car(created_at, due_at, effort)
            car_service.park_car(db, manager_p, car_id, floor.id, spot.id, now=parked_at)
            if rng.random() < 0.2:
                hazard_at = parked_at + (now - parked_at) * rng.uniform(0.1, 0.6)
                car_service.set_hazard(db, owner_p, car_id, True, now=hazard_at)
        db.commit()

    # Pátio: tarefas criadas e ainda não distribuídas.
    for _ in range(9):
        created_at = now - timedelta(hours=rng.uniform(1, 72))
        new_car(created_at, now + timedelta(days=rng.uniform(-1, 7)))
    db.commit()

    print("Seed concluído. Senha de todos: senha123")
    print(f"  Gestora:            {manager.email}")
    print(f"  Manobrista:         {valet.email}")
    print(f"  Dona + manobrista:  {owners[0].email}")
    print(f"  Dono de andar:      {owners[1].email} (e os demais nome.sobrenome@exemplo.com)")
    db.close()


if __name__ == "__main__":
    main()
