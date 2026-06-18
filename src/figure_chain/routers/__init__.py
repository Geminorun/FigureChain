from __future__ import annotations

from fastapi import APIRouter

from figure_chain.routers import ai, chains, encounters, health, people, review


def api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(people.router)
    router.include_router(encounters.router)
    router.include_router(chains.router)
    router.include_router(ai.router)
    router.include_router(review.router)
    return router
