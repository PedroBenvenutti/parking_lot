from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.schemas.user import LoginIn, MeOut, TokenOut
from app.services.auth import authenticate, create_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, db: DB) -> TokenOut:
    user = authenticate(db, body.email, body.password)
    return TokenOut(access_token=create_token(user.id))


@router.get("/me")
def me(p: CurrentUser) -> MeOut:
    return MeOut(
        id=p.user_id,
        name=p.name,
        is_manager=p.is_manager,
        is_valet=p.is_valet,
        owned_floor_id=p.owned_floor_id,
        valet_type_ids=sorted(p.valet_type_ids),
    )
