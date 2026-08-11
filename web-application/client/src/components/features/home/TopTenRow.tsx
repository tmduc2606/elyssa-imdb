import { MediaCard } from "@/components/composites/MediaCard";
import type { TitleSummary } from "@/lib/types";

interface TopTenRowProps {
  titles: TitleSummary[];
}

export function TopTenRow({ titles }: TopTenRowProps) {
  if (titles.length === 0) return null;

  const top = titles.slice(0, 10);

  return (
    <section aria-label="Top 10 this week">
      <h2 className="mb-4 text-2xl font-semibold tracking-tight">Top 10 this week</h2>
      <div className="flex gap-3 overflow-x-auto pb-4 [scrollbar-width:thin]">
        {top.map((title, i) => (
          <div key={title.id} className="relative w-32 shrink-0 sm:w-36 md:w-40">
            <MediaCard
              id={title.id}
              title={title.primaryTitle}
              year={title.startYear}
              rating={title.averageRating}
              genres={title.genres}
              posterUrl={title.posterUrl}
            />
            <span
              aria-hidden="true"
              className="pointer-events-none absolute -bottom-1 left-1 text-6xl font-black leading-none text-foreground/80 sm:text-7xl"
            >
              {i + 1}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
