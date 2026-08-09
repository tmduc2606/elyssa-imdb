import { EntityLink } from "@/components/composites/EntityLink";
import { Skeleton } from "@/components/ui/skeleton";
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

  const actors = cast.filter((c) => c.category === "actor" || c.category === "actress");
  const crewList = crew ?? cast.filter((c) => c.category !== "actor" && c.category !== "actress");
  const directors = crewList.filter((c) => c.category === "director");
  const writers = crewList.filter((c) => c.category === "writer");
  const otherCrew = crewList.filter((c) => c.category !== "director" && c.category !== "writer");

  const sections: Array<{ title: string; members: TitlePrincipal[] }> = [];
  if (actors.length > 0) sections.push({ title: "Cast", members: actors });
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
            {section.members.map((member) => (
              <div
                key={`${member.person.id}-${member.character}-${member.job}`}
                className="flex items-center justify-between"
              >
                <EntityLink
                  id={member.person.id}
                  name={member.person.primaryName}
                  type="person"
                  posterUrl={member.person.posterUrl}
                />
                {member.character ? (
                  <span className="text-sm text-muted">{member.character}</span>
                ) : (
                  <span className="text-sm text-muted">{member.job ?? member.category}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
