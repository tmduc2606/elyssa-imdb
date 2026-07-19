import { useGoldQuery } from "@/hooks/useGoldQuery";
import { QUERY_STALE_TIME } from "@/lib/constants";
import type {
  TitleDetail,
  PersonDetail,
  TitleSummary,
  RatingSnapshot,
  PaginatedResult,
} from "@/lib/types";

export const TITLE_DETAIL_QUERY = `
  query TitleDetail($tconst: ID!) {
    title(tconst: $tconst) {
      id
      primaryTitle
      originalTitle
      titleType
      startYear
      endYear
      runtimeMinutes
      genres
      averageRating
      numVotes
      posterUrl
      cast(limit: 20) {
        person { id primaryName posterUrl }
        character
        ordering
        category
        job
      }
      crew {
        person { id primaryName posterUrl }
        category
        job
      }
      similar(limit: 12) {
        id primaryTitle averageRating posterUrl startYear genres
      }
      episodes(limit: 100) {
        seasonNumber
        episodeNumber
        title { id primaryTitle }
      }
    }
  }
`;

export const PERSON_DETAIL_QUERY = `
  query PersonDetail($nconst: ID!) {
    person(nconst: $nconst) {
      id
      primaryName
      birthYear
      deathYear
      primaryProfession
      posterUrl
      knownForTitles(limit: 10) {
        id primaryTitle averageRating posterUrl startYear genres
      }
      filmography(limit: 50) {
        title { id primaryTitle averageRating posterUrl startYear genres }
        category
        character
        year
      }
      collaborators(limit: 20) {
        person { id primaryName posterUrl }
        collaborationCount
      }
    }
  }
`;

export const SEARCH_QUERY = `
  query Search($query: String!, $first: Int, $after: String) {
    search(query: $query, first: $first, after: $after) {
      items {
        ... on Title {
          id primaryTitle titleType startYear averageRating posterUrl genres
        }
        ... on Person {
          id primaryName birthYear primaryProfession posterUrl
        }
      }
      total
      hasMore
      cursor
    }
  }
`;

export const BROWSE_QUERY = `
  query Browse($genres: [String!], $decade: Int, $titleType: String, $minRating: Float, $sortBy: String, $first: Int, $after: String) {
    browse(genres: $genres, decade: $decade, titleType: $titleType, minRating: $minRating, sortBy: $sortBy, first: $first, after: $after) {
      items {
        id primaryTitle titleType startYear averageRating numVotes posterUrl genres
      }
      total
      hasMore
      cursor
    }
  }
`;

export const HOME_PAGE_QUERY = `
  query HomePage {
    trending(limit: 20) {
      id primaryTitle titleType startYear averageRating numVotes posterUrl genres
    }
    topRated(limit: 20) {
      id primaryTitle titleType startYear averageRating numVotes posterUrl genres
    }
    featured(limit: 10) {
      id primaryTitle titleType startYear averageRating posterUrl genres
    }
  }
`;

export const TITLE_RATINGS_QUERY = `
  query TitleRatings($tconst: ID!, $days: Int) {
    titleRatings(tconst: $tconst, days: $days) {
      snapshotDate averageRating numVotes
    }
  }
`;

interface HomePageData {
  trending: TitleSummary[];
  topRated: TitleSummary[];
  featured: TitleSummary[];
}

export function useTitleDetail(tconst: string) {
  return useGoldQuery<TitleDetail>({
    query: TITLE_DETAIL_QUERY,
    variables: { tconst },
    queryKey: ["title", tconst],
    staleTime: QUERY_STALE_TIME.titleDetail,
    enabled: !!tconst,
  });
}

export function usePersonDetail(nconst: string) {
  return useGoldQuery<PersonDetail>({
    query: PERSON_DETAIL_QUERY,
    variables: { nconst },
    queryKey: ["person", nconst],
    staleTime: QUERY_STALE_TIME.personDetail,
    enabled: !!nconst,
  });
}

export function useSearch(query: string) {
  return useGoldQuery<{ search: PaginatedResult<TitleSummary> }>({
    query: SEARCH_QUERY,
    variables: { query, first: 50 },
    queryKey: ["search", query],
    staleTime: QUERY_STALE_TIME.search,
    enabled: query.length > 0,
  });
}

export function useBrowse(filters: {
  genres?: string[];
  decade?: number | null;
  titleType?: string | null;
  minRating?: number | null;
  sortBy?: string;
}) {
  return useGoldQuery<{ browse: PaginatedResult<TitleSummary> }>({
    query: BROWSE_QUERY,
    variables: {
      genres: filters.genres?.length ? filters.genres : undefined,
      decade: filters.decade ?? undefined,
      titleType: filters.titleType ?? undefined,
      minRating: filters.minRating ?? undefined,
      sortBy: filters.sortBy ?? "rating",
      first: 100,
    },
    queryKey: ["browse", filters],
    staleTime: QUERY_STALE_TIME.browse,
  });
}

export function useHomePage() {
  return useGoldQuery<HomePageData>({
    query: HOME_PAGE_QUERY,
    queryKey: ["home"],
    staleTime: QUERY_STALE_TIME.trending,
  });
}

export function useTitleRatings(tconst: string, days?: number) {
  return useGoldQuery<{ titleRatings: RatingSnapshot[] }>({
    query: TITLE_RATINGS_QUERY,
    variables: { tconst, days },
    queryKey: ["titleRatings", tconst, days],
    staleTime: QUERY_STALE_TIME.titleDetail,
    enabled: !!tconst,
  });
}
