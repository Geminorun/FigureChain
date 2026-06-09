from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from figure_chain.errors import register_error_handlers
from figure_chain.routers import api_router
from figure_data.config import load_settings
from figure_data.db.session import create_db_engine
from figure_data.graph.neo4j_client import create_neo4j_driver
from figure_data.graph.types import GraphConfigError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    engine = create_db_engine(settings)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    neo4j_driver = None
    neo4j_config_error: GraphConfigError | None = None
    try:
        neo4j_driver = create_neo4j_driver(settings)
    except GraphConfigError as exc:
        neo4j_config_error = exc
    app.state.settings = settings
    app.state.db_engine = engine
    app.state.pg_session_factory = session_factory
    app.state.neo4j_driver = neo4j_driver
    app.state.neo4j_database = settings.neo4j_database or "neo4j"
    app.state.neo4j_config_error = neo4j_config_error
    try:
        yield
    finally:
        if neo4j_driver is not None:
            neo4j_driver.close()
        engine.dispose()


def create_app(*, lifespan_enabled: bool = True) -> FastAPI:
    app = FastAPI(
        title="FigureChain API",
        version="0.1.0",
        lifespan=lifespan if lifespan_enabled else None,
    )
    register_error_handlers(app)
    app.include_router(api_router())
    return app
