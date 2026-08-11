export interface Title {
  id: string;
  primaryTitle: string;
  originalTitle: string | null;
  titleType: TitleType;
  startYear: number | null;
  endYear: number | null;
  runtimeMinutes: number | null;
  genres: string[];
  averageRating: number | null;
  numVotes: number | null;
  posterUrl: string | null;
  parentTconst: string | null;
  seriesTitle: string | null;
  seasonNumber: number | null;
  episodeNumber: number | null;
  popularitySegment: string | null;
}

export type TitleType =
  | "movie"
  | "tvSeries"
  | "tvMiniSeries"
  | "tvMovie"
  | "tvEpisode"
  | "tvSpecial"
  | "short"
  | "video";

export interface TitleDetail extends Title {
  overview: string | null;
  tagline: string | null;
  cast: TitlePrincipal[];
  crew: TitlePrincipal[];
  episodes: EpisodeContent[];
  similar: TitleSummary[];
  ratings: RatingSnapshot[];
}

export interface TitleSummary {
  id: string;
  primaryTitle: string;
  averageRating: number | null;
  posterUrl: string | null;
  startYear: number | null;
  genres: string[];
}

export interface Person {
  id: string;
  primaryName: string;
  birthYear: number | null;
  deathYear: number | null;
  primaryProfession: string[];
  knownForTitles: TitleSummary[];
  posterUrl: string | null;
}

export interface PersonDetail extends Person {
  filmography: FilmographyEntry[];
  collaborators: Collaborator[];
  careerTimeline: CareerYear[];
}

export interface FilmographyEntry {
  title: TitleSummary;
  category: PrincipalCategory;
  character: string | null;
  year: number | null;
}

export interface Collaborator {
  person: PersonSummary;
  collaborationCount: number;
  titles: TitleSummary[];
}

export interface PersonSummary {
  id: string;
  primaryName: string | null;
  headshotUrl: string | null;
  posterUrl: string | null;
}

export interface TitlePrincipal {
  person: PersonSummary;
  character: string | null;
  ordering: number | null;
  category: PrincipalCategory;
  job: string | null;
}

export type PrincipalCategory =
  | "actor"
  | "actress"
  | "director"
  | "writer"
  | "producer"
  | "composer"
  | "cinematographer"
  | "editor"
  | "production_designer"
  | "self"
  | string;

export interface EpisodeContent {
  seasonNumber: number | null;
  episodeNumber: number | null;
  title: TitleSummary | null;
}

export interface RatingSnapshot {
  snapshotDate: string;
  averageRating: number;
  numVotes: number;
}

export interface CareerYear {
  year: number;
  titles: TitleSummary[];
}

export interface BrowseFilters {
  genres: string[];
  decade: number | null;
  titleType: TitleType | null;
  minRating: number | null;
  sortBy: BrowseSort;
}

export type BrowseSort = "rating" | "votes" | "year" | "title";

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  hasMore: boolean;
  cursor: string | null;
}

export interface WatchlistItem {
  id: string;
  title: TitleSummary;
  addedAt: string;
  notes: string | null;
}

export interface User {
  id: string;
  email: string;
  displayName: string;
}

export interface AuthTokens {
  accessToken: string;
  expiresIn: number;
}
