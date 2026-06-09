from __future__ import annotations

from fastapi import APIRouter

from figure_chain.routers import health, people


def api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(people.router)
    return router
