import { EntityLink } from "@/components/composites/EntityLink";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRole } from "@/lib/utils";
import type { TitlePrincipal } from "@/lib/types";

interface CastListProps {
  cast: TitlePrincipal[];
  crew?: TitlePrincipal[];
  isLoading?: boolean;
}

export function CastList({ cast, crew, isLoading }: CastListProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <Skeleton className="size-8 rounded-full" />
            <Skeleton className="h-4 w-32" />
          </div>
        ))}
      </div>
    );
  }

  const ACTOR_CATEGORIES = new Set(["actor", "actress", "self"]);
  const actors = cast.filter((c) => ACTOR_CATEGORIES.has(c.category));
  // Unknown actors are pure noise — hide them entirely (owner decision §6 Q1).
  const knownActors = actors.filter((c) => c.person.primaryName);
  const crewList = crew ?? cast.filter((c) => !ACTOR_CATEGORIES.has(c.category));
  const directors = crewList.filter((c) => c.category === "director");
  const writers = crewList.filter((c) => c.category === "writer");
  const otherCrew = crewList.filter((c) => c.category !== "director" && c.category !== "writer");

  const sections: Array<{ title: string; members: TitlePrincipal[] }> = [];
  if (knownActors.length > 0) sections.push({ title: "Cast", members: knownActors });
  if (directors.length > 0) sections.push({ title: "Directors", members: directors });
  if (writers.length > 0) sections.push({ title: "Writers", members: writers });
  if (otherCrew.length > 0) sections.push({ title: "Crew", members: otherCrew });

  if (sections.length === 0) return null;

  return (
    <div className="flex flex-col gap-6">
      {sections.map((section) => (
        <div key={section.title}>
          <h3 className="mb-3 text-sm font-medium text-muted">{section.title}</h3>
          <div className="flex flex-col gap-2">
            {section.members.map((member, i) => (
              <div
                key={`${member.person.id}-${member.ordering ?? i}`}
                className="flex items-center justify-between gap-4"
              >
                <EntityLink
                  id={member.person.id}
                  name={member.person.primaryName}
                  type="person"
                  posterUrl={member.person.headshotUrl ?? member.person.posterUrl}
                />
                <span className="truncate text-right text-sm text-muted">
                  {formatRole(member.category, member.job, member.character)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}