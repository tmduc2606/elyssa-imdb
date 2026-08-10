import { useRef, useEffect, useState } from "react";
import { Clock, Calendar } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { cn, formatRuntime, formatYear } from "@/lib/utils";
import { RatingBadge } from "@/components/composites/RatingBadge";
import { GenreTags } from "@/components/composites/GenreTags";
import { WatchlistButton } from "@/components/composites/WatchlistButton";
import { useWatchlistState } from "@/hooks/useWatchlist";
import { FEATURE_FLAGS } from "@/lib/constants";
import type { Title } from "@/lib/types";

gsap.registerPlugin(ScrollTrigger);

type TitleHeroTitle = Title & {
  overview?: string | null;
  tagline?: string | null;
};

interface TitleHeroProps {
  title: TitleHeroTitle;
  className?: string;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

export function TitleHero({ title, className }: TitleHeroProps) {
  const posterRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = usePrefersReducedMotion();
  const watchlist = useWatchlistState(title.id);

  useGSAP(() => {
    if (!posterRef.current) return;
    if (!FEATURE_FLAGS.gsapAnimations || prefersReducedMotion) return;
    gsap.fromTo(
      posterRef.current,
      { y: 0 },
      {
        y: -30,
        ease: "none",
        scrollTrigger: {
          trigger: posterRef.current.parentElement,
          start: "top top",
          end: "bottom top",
          scrub: 1,
        },
      },
    );
  }, []);

  return (
    <div className={cn("flex flex-col gap-6 md:flex-row", className)}>
      <div ref={posterRef} className="w-full shrink-0 md:w-64">
        <div className="aspect-[2/3] overflow-hidden rounded-xl bg-muted">
          {title.posterUrl ? (
            <img
              src={title.posterUrl}
              alt={title.primaryTitle}
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
              className="size-full object-cover"
            />
          ) : (
            <div className="flex size-full items-center justify-center bg-surface p-4">
              <span className="text-center text-sm text-muted">{title.primaryTitle}</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              {title.primaryTitle}
            </h1>
            {title.originalTitle && title.originalTitle !== title.primaryTitle && (
              <p className="mt-1 text-sm text-muted">{title.originalTitle}</p>
            )}
            {title.tagline && (
              <p className="mt-2 italic text-muted">“{title.tagline}”</p>
            )}
          </div>
          <WatchlistButton
            isSaved={watchlist.isSaved}
            onToggle={() =>
              watchlist.isSaved && watchlist.entry
                ? watchlist.remove(watchlist.entry.id)
                : watchlist.add({
                    tconst: title.id,
                    title: {
                      id: title.id,
                      primaryTitle: title.primaryTitle,
                      startYear: title.startYear,
                      averageRating: title.averageRating,
                      genres: title.genres,
                      posterUrl: title.posterUrl,
                    },
                  })
            }
            isDisabled={watchlist.isAdding || watchlist.isRemoving}
            saveCount={watchlist.saveCount}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          {title.averageRating != null && (
            <span className="flex items-center gap-1">
              <RatingBadge rating={title.averageRating} size="md" />
              <span className="text-xs text-muted">
                ({title.numVotes?.toLocaleString()} votes)
              </span>
            </span>
          )}
          {title.startYear != null && (
            <span className="flex items-center gap-1">
              <Calendar className="size-3.5" />
              {formatYear(title.startYear, title.endYear)}
            </span>
          )}
          {title.runtimeMinutes != null && (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" />
              {formatRuntime(title.runtimeMinutes)}
            </span>
          )}
          <span className="rounded border border-border px-1.5 py-0.5 text-[11px] uppercase">
            {title.titleType.replace(/([A-Z])/g, " $1").trim()}
          </span>
        </div>

        {title.genres.length > 0 && <GenreTags genres={title.genres} />}
        {title.overview && (
          <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted">
            {title.overview}
          </p>
        )}
      </div>
    </div>
  );
}