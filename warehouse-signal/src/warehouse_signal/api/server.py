"""FastAPI server for the Warehouse Signal frontend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from warehouse_signal.api.deps import close_storage, init_storage
from warehouse_signal.config import Config
from warehouse_signal.api.demo_routes import router as demo_router
from warehouse_signal.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_storage()
    yield
    close_storage()


app = FastAPI(
    title="Warehouse Signal API",
    description="Earnings call analysis for warehouse expansion signals",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in Config.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(demo_router, prefix="/api")
