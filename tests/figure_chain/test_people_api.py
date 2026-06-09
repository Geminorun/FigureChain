from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_people_service
from figure_chain.schemas import PeopleSearchResponse, PersonSearchItem


class FakePeopleService:
    def search(self, query: str, limit: int) -> PeopleSearchResponse:
        return PeopleSearchResponse(
            query=query,
            limit=limit,
            items=[
                PersonSearchItem(
                    person_id="person-1",
                    display_name="韓琦",
                    primary_name_zh_hant="韓琦",
                    primary_name_zh_hans="韩琦",
                    primary_name_romanized="Han Qi",
                    birth_year=1008,
                    death_year=1075,
                    index_year=630,
                    dynasty_code=None,
                    matching_aliases=[],
                    external_ids=["630"],
                )
            ],
        )


def test_people_search_returns_items() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: FakePeopleService()

    with TestClient(app) as client:
        response = client.get("/api/v1/people/search", params={"q": "韓琦", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "韓琦"
    assert body["items"][0]["display_name"] == "韓琦"


def test_people_search_rejects_blank_query() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_people_service] = lambda: FakePeopleService()

    with TestClient(app) as client:
        response = client.get("/api/v1/people/search", params={"q": ""})

    assert response.status_code == 422
