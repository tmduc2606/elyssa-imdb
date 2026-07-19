import { Link } from "react-router";

import { RatingBadge } from "@/components/composites/RatingBadge";
import type { TitleSummary } from "@/lib/types";

interface FeaturedCarouselProps {
  titles: TitleSummary[];
}

export function FeaturedCarousel({ titles }: FeaturedCarouselProps) {
  if (titles.length === 0) return null;

  return (
    <section
      aria-label="Featured titles"
      aria-roledescription="carousel"
      className="relative overflow-hidden rounded-xl bg-surface"
    >
      <div
        role="list"
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-4 pt-4"
      >
        {titles.map((title, index) => (
          <Link
            key={title.id}
            to={`/title/${title.id}`}
            role="listitem"
            aria-roledescription="slide"
            aria-label={`Slide ${index + 1}: ${title.primaryTitle}`}
            className="group relative min-w-[280px] snap-start overflow-hidden rounded-lg border border-border"
          >
            <div className="aspect-[16/9] bg-muted">
              {title.posterUrl && (
                <img
                  src={title.posterUrl}
                  alt={title.primaryTitle}
                  loading="lazy"
                  className="size-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
              )}
            </div>
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
            <div className="absolute bottom-0 left-0 right-0 p-4 text-white">
              <h3 className="truncate text-lg font-semibold">{title.primaryTitle}</h3>
              <div className="mt-1 flex items-center gap-2">
                {title.averageRating != null && (
                  <RatingBadge rating={title.averageRating} />
                )}
                {title.startYear && (
                  <span className="text-sm text-white/80">{title.startYear}</span>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
