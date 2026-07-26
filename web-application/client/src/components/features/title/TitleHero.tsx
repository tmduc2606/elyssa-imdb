import { useRef } from "react";
import { Clock, Calendar } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { cn, formatRuntime, formatYear } from "@/lib/utils";
import { RatingBadge } from "@/components/composites/RatingBadge";
import { GenreTags } from "@/components/composites/GenreTags";
import { WatchlistButton } from "@/components/composites/WatchlistButton";
import type { Title } from "@/lib/types";

gsap.registerPlugin(ScrollTrigger);

interface TitleHeroProps {
  title: Title;
  className?: string;
}

export function TitleHero({ title, className }: TitleHeroProps) {
  const posterRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (!posterRef.current) return;
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
              className="size-full object-cover"
            />
          ) : (
            <div className="flex size-full items-center justify-center bg-surface p-4">
              <span className="text-center text-sm text-muted">{title.primaryTitle}</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              {title.primaryTitle}
            </h1>
            {title.originalTitle && title.originalTitle !== title.primaryTitle && (
              <p className="mt-1 text-sm text-muted">{title.originalTitle}</p>
            )}
          </div>
          <WatchlistButton />
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
      </div>
    </div>
  );
}
