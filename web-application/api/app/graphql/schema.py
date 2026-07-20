from __future__ import annotations

import strawberry

from app.graphql.resolvers import (
    resolve_browse,
    resolve_homepage,
    resolve_person,
    resolve_search,
    resolve_title,
    resolve_title_ratings,
    resolve_trending,
    resolve_top_rated,
    resolve_featured,
)
from app.graphql.types import (
    HomePageData,
    PaginatedTitles,
    Person,
    RatingSnapshot,
    TitleDetail,
    TitleSummary,
)


@strawberry.type
class Query:
    @strawberry.field
    def title(self, tconst: str) -> TitleDetail | None:
        return resolve_title(tconst)

    @strawberry.field
    def person(self, nconst: str) -> Person | None:
        return resolve_person(nconst)

    @strawberry.field
    def search(
        self, query: str, first: int | None = 50, after: str | None = None
    ) -> PaginatedTitles | None:
        items = resolve_search(query, first or 50)
        return PaginatedTitles(items=items, total=len(items), has_more=False, cursor=None)

    @strawberry.field
    def browse(
        self,
        genres: list[str] | None = None,
        decade: int | None = None,
        title_type: str | None = None,
        min_rating: float | None = None,
        sort_by: str | None = None,
        first: int | None = 100,
        after: str | None = None,
    ) -> PaginatedTitles | None:
        items = resolve_browse(genres, decade, title_type, min_rating, sort_by, first or 100)
        return PaginatedTitles(items=items, total=len(items), has_more=False, cursor=None)

    @strawberry.field
    def homepage(self) -> HomePageData | None:
        return resolve_homepage()

    @strawberry.field
    def trending(self, limit: int | None = 20) -> list[TitleSummary]:
        return resolve_trending(limit or 20)

    @strawberry.field
    def top_rated(self, limit: int | None = 20) -> list[TitleSummary]:
        return resolve_top_rated(limit or 20)

    @strawberry.field
    def featured(self, limit: int | None = 10) -> list[TitleSummary]:
        return resolve_featured(limit or 10)

    @strawberry.field
    def title_ratings(
        self, tconst: str, days: int | None = None
    ) -> list[RatingSnapshot]:
        return resolve_title_ratings(tconst)


schema = strawberry.Schema(query=Query)
