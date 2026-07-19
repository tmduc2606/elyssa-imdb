import { Link } from "react-router";
import { cn } from "@/lib/utils";
import { GENRES } from "@/lib/constants";

const genreAccents: Record<string, string> = {
  Action: "bg-accent-red-bg text-accent-red-text",
  Comedy: "bg-accent-yellow-bg text-accent-yellow-text",
  Drama: "bg-accent-blue-bg text-accent-blue-text",
  Horror: "bg-accent-red-bg text-accent-red-text",
  Romance: "bg-accent-red-bg text-accent-red-text",
  "Sci-Fi": "bg-accent-blue-bg text-accent-blue-text",
  Documentary: "bg-accent-green-bg text-accent-green-text",
  Thriller: "bg-accent-blue-bg text-accent-blue-text",
};

export function GenreQuickLinks() {
  const displayGenres = GENRES.filter((g) =>
    ["Action", "Comedy", "Drama", "Horror", "Sci-Fi", "Documentary", "Romance", "Thriller", "Animation", "Mystery"].includes(g),
  );

  return (
    <section>
      <h2 className="mb-4 text-2xl font-semibold tracking-tight">Browse by genre</h2>
      <div className="flex flex-wrap gap-2">
        {displayGenres.map((genre) => (
          <Link
            key={genre}
            to={`/browse/genre/${genre.toLowerCase()}`}
            className={cn(
              "rounded-full px-4 py-2 text-sm font-medium transition-opacity hover:opacity-80",
              genreAccents[genre] ?? "bg-surface text-muted border border-border",
            )}
          >
            {genre}
          </Link>
        ))}
      </div>
    </section>
  );
}
