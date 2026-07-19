import { Link } from "react-router";
import { cn, formatYear } from "@/lib/utils";
import { usePreloadOnHover } from "@/hooks/usePreloadOnHover";
import { RatingBadge } from "./RatingBadge";
import { GenreTags } from "./GenreTags";

interface MediaCardProps {
  id: string;
  title: string;
  year?: number | null;
  rating?: number | null;
  genres?: string[];
  posterUrl?: string | null;
  className?: string;
}

export function MediaCard({
  id,
  title,
  year,
  rating,
  genres,
  posterUrl,
  className,
}: MediaCardProps) {
  const { preload, cancelPreload } = usePreloadOnHover();

  return (
    <Link
      to={`/title/${id}`}
      aria-label={`View details for ${title}`}
      onMouseEnter={() => preload(id)}
      onMouseLeave={cancelPreload}
      className={cn(
        "group flex flex-col gap-2 rounded-xl border border-border bg-card p-2 transition-all hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)]",
        className,
      )}
    >
      <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-muted">
        {posterUrl ? (
          <img
            src={posterUrl}
            alt={title}
            loading="lazy"
            className="size-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex size-full items-center justify-center bg-surface p-4">
            <span className="text-center text-xs text-muted">{title}</span>
          </div>
        )}
        {rating != null && (
          <div className="absolute left-2 top-2">
            <RatingBadge rating={rating} />
          </div>
        )}
      </div>
      <div className="flex flex-col gap-1 px-0.5 pb-1">
        <h3 className="truncate text-sm font-medium leading-tight">{title}</h3>
        <div className="flex items-center gap-2 text-xs text-muted">
          {year != null && <span>{formatYear(year)}</span>}
        </div>
        {genres && genres.length > 0 && (
          <GenreTags genres={genres} limit={2} />
        )}
      </div>
    </Link>
  );
}
