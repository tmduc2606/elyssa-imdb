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

export type FeatureFlagKey =
  | "genrePrediction"
  | "ratingPrediction"
  | "watchlist"
  | "recommendations"
  | "gsapAnimations";

export const FEATURE_FLAGS: Record<FeatureFlagKey, boolean> = {
  genrePrediction: import.meta.env.VITE_FF_GENRE_PREDICTION !== "false",
  ratingPrediction: import.meta.env.VITE_FF_RATING_PREDICTION !== "false",
  watchlist: import.meta.env.VITE_FF_WATCHLIST !== "false",
  recommendations: import.meta.env.VITE_FF_RECOMMENDATIONS === "true",
  gsapAnimations: import.meta.env.VITE_FF_GSAP_ANIMATIONS !== "false",
};

export const ROLE_LABELS: Record<string, string> = {
  actor: "Actor",
  actress: "Actress",
  self: "Self",
  archive_footage: "Archive Footage",
  archive_sound: "Archive Sound",
  director: "Director",
  writer: "Writer",
  producer: "Producer",
  executive_producer: "Executive Producer",
  composer: "Composer",
  cinematographer: "Cinematographer",
  editor: "Editor",
  production_designer: "Production Designer",
  casting_director: "Casting Director",
  costume_designer: "Costume Designer",
  makeup_department: "Makeup Department",
  camera_department: "Camera Department",
  art_department: "Art Department",
  sound_department: "Sound Department",
  visual_effects: "Visual Effects",
  special_effects: "Special Effects",
  stunts: "Stunts",
  animation_department: "Animation Department",
  music_department: "Music Department",
  script_department: "Script Department",
  transportation_department: "Transportation Department",
  editorial_department: "Editorial Department",
  location_management: "Location Management",
  casting: "Casting",
  production_manager: "Production Manager",
  assistant_director: "Assistant Director",
  second_unit_director: "Second Unit Director",
  choreographer: "Choreographer",
  writer_soundtrack: "Soundtrack",
  editorial_services: "Editorial Services",
  itself: "Itself",
};

export const EPISODIC_TITLE_TYPES = new Set([
  "tvSeries",
  "tvMiniSeries",
  "tvMovie",
  "tvSpecial",
]);
