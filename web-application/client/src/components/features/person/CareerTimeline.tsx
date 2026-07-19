import { Link } from "react-router";
import { EmptyState } from "@/components/composites/EmptyState";
import type { CareerYear } from "@/lib/types";

interface CareerTimelineProps {
  timeline: CareerYear[];
}

export function CareerTimeline({ timeline }: CareerTimelineProps) {
  if (timeline.length === 0) return <EmptyState title="No career data" />;

  return (
    <section>
      <h3 className="mb-4 text-lg font-semibold">Career timeline</h3>
      <div className="relative flex flex-col gap-6 pl-6 before:absolute before:bottom-0 before:left-2.5 before:top-0 before:w-px before:bg-border">
        {timeline.map((year) => (
          <div key={year.year} className="relative">
            <div className="absolute -left-[18px] top-1 size-2 rounded-full bg-border" />
            <span className="mb-2 block text-sm font-medium text-muted">{year.year}</span>
            <div className="flex flex-col gap-1">
              {year.titles.map((title) => (
                <Link
                  key={title.id}
                  to={`/title/${title.id}`}
                  className="truncate rounded-lg px-3 py-1.5 text-sm hover:bg-muted"
                >
                  {title.primaryTitle}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
