from __future__ import annotations

from fastapi import APIRouter

from figure_chain.routers import encounters, health, people


def api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(people.router)
    router.include_router(encounters.router)
    return router
