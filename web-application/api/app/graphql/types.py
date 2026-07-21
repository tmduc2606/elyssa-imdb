from __future__ import annotations

from typing import TYPE_CHECKING

import strawberry

if TYPE_CHECKING:
    pass


@strawberry.type
class Title:
    id: str
    primary_title: str
    original_title: str | None = None
    title_type: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    runtime_minutes: int | None = None
    genres: list[str] = strawberry.field(default_factory=list)
    average_rating: float | None = None
    num_votes: int | None = None
    poster_url: str | None = None
    parent_tconst: str | None = None
    series_title: str | None = None
    season_number: int | None = None
    episode_number: int | None = None


@strawberry.type
class PersonSummary:
    id: str
    primary_name: str
    poster_url: str | None = None


@strawberry.type
class CastMember:
    person: PersonSummary
    character: str | None = None
    ordering: int | None = None
    category: str | None = None
    job: str | None = None


@strawberry.type
class CrewMember:
    person: PersonSummary
    category: str | None = None
    job: str | None = None


@strawberry.type
class TitleSummary:
    id: str
    primary_title: str
    title_type: str | None = None
    start_year: int | None = None
    average_rating: float | None = None
    num_votes: int | None = None
    poster_url: str | None = None
    genres: list[str] = strawberry.field(default_factory=list)


@strawberry.type
class EpisodeContent:
    season_number: int | None = None
    episode_number: int | None = None
    title: TitleSummary | None = None


@strawberry.type
class RatingSnapshot:
    snapshot_date: str
    average_rating: float
    num_votes: int


@strawberry.type
class TitleDetail(Title):
    ratings: list[RatingSnapshot] = strawberry.field(default_factory=list)

    @strawberry.field
    def cast(self, limit: int = 20) -> list[CastMember]:
        from app.graphql.resolvers import _resolve_cast as rc
        return rc(self.id, limit)

    @strawberry.field
    def crew(self) -> list[CrewMember]:
        from app.graphql.resolvers import _resolve_crew as rc
        return rc(self.id)

    @strawberry.field
    def episodes(self, limit: int = 100) -> list[EpisodeContent]:
        from app.graphql.resolvers import _resolve_episodes as re
        return re(self.id, limit)

    @strawberry.field
    def similar(self, limit: int = 12) -> list[TitleSummary]:
        from app.graphql.resolvers import _resolve_similar as rs
        return rs(self.id, self.genres, limit)


@strawberry.type
class Person:
    id: str
    primary_name: str
    birth_year: int | None = None
    death_year: int | None = None
    primary_profession: list[str] = strawberry.field(default_factory=list)
    poster_url: str | None = None
    known_for_titles: list[TitleSummary] = strawberry.field(default_factory=list)
    filmography: list[FilmographyEntry] = strawberry.field(default_factory=list)
    collaborators: list[Collaborator] = strawberry.field(default_factory=list)


@strawberry.type
class FilmographyEntry:
    title: TitleSummary
    category: str | None = None
    character: str | None = None
    year: int | None = None


@strawberry.type
class Collaborator:
    person: PersonSummary
    collaboration_count: int | None = None
    titles: list[TitleSummary] = strawberry.field(default_factory=list)


@strawberry.type
class PaginatedTitles:
    items: list[TitleSummary]
    total: int
    has_more: bool
    cursor: str | None = None


@strawberry.type
class HomePageData:
    trending: list[TitleSummary]
    top_rated: list[TitleSummary]
    featured: list[TitleSummary]
