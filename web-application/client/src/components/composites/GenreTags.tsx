import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface GenreTagsProps {
  genres: string[];
  limit?: number;
  className?: string;
}

const genreAccent: Record<string, string> = {
  Action: "bg-accent-red-bg text-accent-red-text",
  Comedy: "bg-accent-yellow-bg text-accent-yellow-text",
  Drama: "bg-accent-blue-bg text-accent-blue-text",
  Horror: "bg-accent-red-bg text-accent-red-text",
  Romance: "bg-accent-red-bg text-accent-red-text",
  Thriller: "bg-accent-blue-bg text-accent-blue-text",
  Documentary: "bg-accent-green-bg text-accent-green-text",
  SciFi: "bg-accent-blue-bg text-accent-blue-text",
};

function getGenreStyle(genre: string): string {
  return genreAccent[genre] ?? "bg-surface text-muted border border-border";
}

export function GenreTags({ genres, limit, className }: GenreTagsProps) {
  const visible = limit ? genres.slice(0, limit) : genres;
  const remaining = limit ? genres.length - limit : 0;

  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {visible.map((genre) => (
        <Badge
          key={genre}
          variant="outline"
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider",
            getGenreStyle(genre),
          )}
        >
          {genre}
        </Badge>
      ))}
      {remaining > 0 && (
        <span className="text-[11px] text-muted">+{remaining}</span>
      )}
    </div>
  );
}
