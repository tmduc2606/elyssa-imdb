// API endpoints — defaults use Vite dev proxy (/graphql → backend, /auth → backend)
// Override via VITE_API_URL / VITE_AUTH_URL env vars for production
export const API_URL = import.meta.env.VITE_API_URL ?? "/graphql";
export const AUTH_URL = import.meta.env.VITE_AUTH_URL ?? "/auth";

export const QUERY_TTL = {
  titleDetail: 5 * 60 * 1000,
  personDetail: 10 * 60 * 1000,
  search: 2 * 60 * 1000,
  browse: 5 * 60 * 1000,
  trending: 10 * 60 * 1000,
  watchlist: 30 * 1000,
} as const;

export const QUERY_STALE_TIME = {
  titleDetail: 60 * 1000,
  personDetail: 2 * 60 * 1000,
  search: 30 * 1000,
  browse: 60 * 1000,
  trending: 2 * 60 * 1000,
  watchlist: 0,
} as const;

export const TITLE_TYPES = [
  "movie",
  "tvSeries",
  "tvMiniSeries",
  "tvMovie",
  "tvEpisode",
  "tvSpecial",
  "short",
  "video",
] as const;

export const GENRES = [
  "Action", "Adult", "Adventure", "Animation", "Biography", "Comedy",
  "Crime", "Documentary", "Drama", "Family", "Fantasy", "Film-Noir",
  "Game-Show", "History", "Horror", "Music", "Musical", "Mystery",
  "News", "Reality-TV", "Romance", "Sci-Fi", "Short", "Sport",
  "Talk-Show", "Thriller", "War", "Western",
] as const;
