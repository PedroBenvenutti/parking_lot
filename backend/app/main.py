import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, cars, floors
from app.config import get_settings
from app.services.errors import DomainError
from app.ws import routes as ws_routes
from app.ws.clock_ticker import run_clock_ticker


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ticker = None
    if get_settings().clock_tick_seconds > 0:
        ticker = asyncio.create_task(run_clock_ticker())
    yield
    if ticker:
        ticker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ticker


app = FastAPI(title="Parking Lot de tarefas", lifespan=lifespan)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


for module in (auth, floors, cars, admin):
    app.include_router(module.router, prefix="/api")
app.include_router(ws_routes.router)

# Em produção o build do frontend é servido pelo próprio backend.
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
