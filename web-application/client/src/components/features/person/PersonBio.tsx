import { Calendar, Skull } from "lucide-react";
import { cn, formatYear } from "@/lib/utils";
import type { Person } from "@/lib/types";

interface PersonBioProps {
  person: Person;
  className?: string;
}

export function PersonBio({ person, className }: PersonBioProps) {
  return (
    <div className={cn("flex flex-col gap-4 md:flex-row", className)}>
      <div className="w-full shrink-0 md:w-48">
        <div className="aspect-[2/3] overflow-hidden rounded-xl bg-muted">
          {person.posterUrl ? (
            <img
              src={person.posterUrl}
              alt={person.primaryName}
              loading="lazy"
              className="size-full object-cover"
            />
          ) : (
            <div className="flex size-full items-center justify-center bg-surface">
              <span className="text-4xl font-display text-muted">
                {person.primaryName.charAt(0)}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
          {person.primaryName}
        </h1>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          {person.birthYear != null && (
            <span className="flex items-center gap-1">
              <Calendar className="size-3.5" />
              {formatYear(person.birthYear, person.deathYear)}
            </span>
          )}
          {person.deathYear != null && (
            <span className="flex items-center gap-1 text-accent-red-text">
              <Skull className="size-3.5" />
              Deceased
            </span>
          )}
        </div>
        {person.primaryProfession.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {person.primaryProfession.map((prof) => (
              <span
                key={prof}
                className="rounded-full border border-border px-2.5 py-0.5 text-[11px] text-muted uppercase tracking-wider"
              >
                {prof}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
