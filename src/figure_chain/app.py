from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from figure_chain.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(*, lifespan_enabled: bool = True) -> FastAPI:
    app = FastAPI(
        title="FigureChain API",
        version="0.1.0",
        lifespan=lifespan if lifespan_enabled else None,
    )
    app.include_router(api_router())
    return app
