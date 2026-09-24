from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    name: str
    is_manager: bool
    is_valet: bool
    owned_floor_id: int | None
    valet_type_ids: list[int]


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    is_manager: bool
    is_valet: bool
    floor_id: int | None
    valet_type_ids: list[int]


class UserCreate(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=6)
    is_manager: bool = False
    is_valet: bool = False
    valet_type_ids: list[int] = []
    floor_capacity: int | None = Field(default=None, ge=1, le=60)


class UserRolesIn(BaseModel):
    is_manager: bool | None = None
    is_valet: bool | None = None
    valet_type_ids: list[int] | None = None
