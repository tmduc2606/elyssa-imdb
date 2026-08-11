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
      <div className="flex items-end gap-0 overflow-x-auto pb-4 [scrollbar-width:thin]">
        {top.map((title, i) => (
          <div key={title.id} className="flex shrink-0 items-end">
            <span
              aria-hidden="true"
              className="pointer-events-none mr-2 flex items-end text-[72px] font-black leading-none text-transparent sm:text-[88px]"
              style={{ WebkitTextStroke: "2px var(--color-foreground)" }}
            >
              {i + 1}
            </span>
            <div className="w-32 sm:w-36 md:w-40">
              <MediaCard
                id={title.id}
                title={title.primaryTitle}
                year={title.startYear}
                rating={title.averageRating}
                genres={title.genres}
                posterUrl={title.posterUrl}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
