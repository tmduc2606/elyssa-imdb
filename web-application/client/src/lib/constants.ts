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

export interface FilterChip {
  label: string;
  value: string;
}

// Single source of truth for all filter chip groups (WA 2.8.2)
export const GENRE_CHIPS: FilterChip[] = GENRES.map((g) => ({ label: g, value: g }));

export const TYPE_CHIPS: FilterChip[] = TITLE_TYPES.map((t) => ({
  label: t.replace(/([A-Z])/g, " $1").trim(),
  value: t,
}));

export const DECADE_CHIPS: FilterChip[] = [
  { label: "2020s", value: "2020" },
  { label: "2010s", value: "2010" },
  { label: "2000s", value: "2000" },
  { label: "1990s", value: "1990" },
  { label: "1980s", value: "1980" },
  { label: "1970s", value: "1970" },
  { label: "1960s", value: "1960" },
  { label: "1950s", value: "1950" },
  { label: "Older", value: "older" },
];

export const SORT_CHIPS: FilterChip[] = [
  { label: "Rating", value: "rating" },
  { label: "Votes", value: "votes" },
  { label: "Year", value: "year" },
  { label: "Title", value: "title" },
];

export const MIN_RATING_CHIPS: FilterChip[] = [
  { label: "Any", value: "" },
  { label: "7+", value: "7" },
  { label: "8+", value: "8" },
];

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
