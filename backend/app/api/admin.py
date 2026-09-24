"""Configuração do gestor: tipos de tarefa, usuários, papéis e tipos por manobrista."""

from fastapi import APIRouter, BackgroundTasks

from app.api.deps import DB, CurrentUser
from app.schemas.car import TaskTypeCreate, TaskTypeOut
from app.schemas.serializers import user_out
from app.schemas.user import UserCreate, UserOut, UserRolesIn
from app.services import users as user_service
from app.services.permissions import load_principal
from app.ws.hub import hub

router = APIRouter(tags=["admin"])


@router.get("/task-types")
def list_task_types(db: DB, p: CurrentUser) -> list[TaskTypeOut]:
    return [TaskTypeOut(id=t.id, name=t.name, icon=t.icon) for t in user_service.list_task_types(db)]


@router.post("/task-types", status_code=201)
def create_task_type(body: TaskTypeCreate, db: DB, p: CurrentUser) -> TaskTypeOut:
    task_type = user_service.create_task_type(db, p, body.name, body.icon)
    db.commit()
    return TaskTypeOut(id=task_type.id, name=task_type.name, icon=task_type.icon)


@router.get("/users")
def list_users(db: DB, p: CurrentUser) -> list[UserOut]:
    return [user_out(u) for u in user_service.list_users(db, p)]


@router.post("/users", status_code=201)
def create_user(body: UserCreate, db: DB, p: CurrentUser) -> UserOut:
    user = user_service.create_user(db, p, **body.model_dump())
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/users/{user_id}")
def update_roles(user_id: int, body: UserRolesIn, db: DB, p: CurrentUser, background: BackgroundTasks) -> UserOut:
    user = user_service.update_roles(db, p, user_id, **body.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(user)
    # Conexões WebSocket abertas desse usuário passam a respeitar os novos papéis.
    background.add_task(hub.update_principal, load_principal(db, user_id))
    return user_out(user)
