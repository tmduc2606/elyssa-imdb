import { EntityLink } from "@/components/composites/EntityLink";
import { Skeleton } from "@/components/ui/skeleton";
import type { TitlePrincipal } from "@/lib/types";

interface CastListProps {
  cast: TitlePrincipal[];
  isLoading?: boolean;
}

export function CastList({ cast, isLoading }: CastListProps) {
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

  if (cast.length === 0) return null;

  const actors = cast.filter((c) => c.category === "actor" || c.category === "actress");
  const crew = cast.filter((c) => c.category !== "actor" && c.category !== "actress");

  return (
    <div className="flex flex-col gap-6">
      {actors.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-muted">Cast</h3>
          <div className="flex flex-col gap-2">
            {actors.map((member) => (
              <div key={`${member.person.id}-${member.character}`} className="flex items-center justify-between">
                <EntityLink
                  id={member.person.id}
                  name={member.person.primaryName}
                  type="person"
                  posterUrl={member.person.posterUrl}
                />
                {member.character && (
                  <span className="text-sm text-muted">{member.character}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {crew.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-muted">Crew</h3>
          <div className="flex flex-col gap-2">
            {crew.map((member) => (
              <div key={`${member.person.id}-${member.job}`} className="flex items-center justify-between">
                <EntityLink
                  id={member.person.id}
                  name={member.person.primaryName}
                  type="person"
                  posterUrl={member.person.posterUrl}
                />
                <span className="text-sm text-muted">{member.job ?? member.category}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
