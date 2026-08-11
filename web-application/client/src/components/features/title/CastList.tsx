import { useState } from "react";
import { Link } from "react-router";
import { ChevronDown, ChevronUp } from "lucide-react";
import { EntityLink } from "@/components/composites/EntityLink";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { formatRole, getInitials } from "@/lib/utils";
import type { TitlePrincipal } from "@/lib/types";

interface CastListProps {
  cast: TitlePrincipal[];
  crew?: TitlePrincipal[];
  isLoading?: boolean;
}

const CAST_PREVIEW_COUNT = 6;

function CastCard({ member }: { member: TitlePrincipal }) {
  const headshot = member.person.headshotUrl ?? member.person.posterUrl;
  return (
    <Link
      to={`/person/${member.person.id}`}
      className="group flex flex-col items-center gap-2 rounded-xl border border-transparent p-3 text-center transition-colors hover:border-border hover:bg-surface"
      aria-label={member.person.primaryName ?? "Person details coming soon"}
    >
      <Avatar className="size-16 rounded-full border border-border">
        {headshot ? <AvatarImage src={headshot} alt={member.person.primaryName ?? ""} /> : null}
        <AvatarFallback className="bg-muted text-sm text-muted">
          {getInitials(member.person.primaryName ?? "?")}
        </AvatarFallback>
      </Avatar>
      <span className="truncate text-sm font-medium group-hover:text-foreground">
        {member.person.primaryName ?? "Details coming soon"}
      </span>
      <span className="line-clamp-2 text-xs leading-tight text-muted">
        {member.character || formatRole(member.category, member.job, null)}
      </span>
    </Link>
  );
}

export function CastList({ cast, crew, isLoading }: CastListProps) {
  const [showAllCast, setShowAllCast] = useState(false);

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex flex-col items-center gap-2 p-3">
            <Skeleton className="size-16 rounded-full" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
    );
  }

  const ACTOR_CATEGORIES = new Set(["actor", "actress", "self"]);
  const actors = cast.filter((c) => ACTOR_CATEGORIES.has(c.category));
  // Q1 (owner): unknown actors are pure noise — hide them entirely.
  const knownActors = actors.filter((c) => c.person.primaryName);
  const crewList = crew ?? cast.filter((c) => !ACTOR_CATEGORIES.has(c.category));
  const directors = crewList.filter((c) => c.category === "director");
  const writers = crewList.filter((c) => c.category === "writer");
  const otherCrew = crewList.filter((c) => c.category !== "director" && c.category !== "writer");

  const crewSections: Array<{ title: string; members: TitlePrincipal[] }> = [];
  if (directors.length > 0) crewSections.push({ title: "Directors", members: directors });
  if (writers.length > 0) crewSections.push({ title: "Writers", members: writers });
  if (otherCrew.length > 0) crewSections.push({ title: "Crew", members: otherCrew });

  if (knownActors.length === 0 && crewSections.length === 0) return null;

  const visibleCast = showAllCast ? knownActors : knownActors.slice(0, CAST_PREVIEW_COUNT);

  return (
    <div className="flex flex-col gap-6">
      {knownActors.length > 0 && (
        <section aria-label="Cast">
          <h3 className="mb-3 text-sm font-medium text-muted">Cast</h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {visibleCast.map((member, i) => (
              <CastCard key={`${member.person.id}-${member.ordering ?? i}`} member={member} />
            ))}
          </div>
          {knownActors.length > CAST_PREVIEW_COUNT && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-3"
              onClick={() => setShowAllCast((v) => !v)}
              aria-expanded={showAllCast}
            >
              {showAllCast ? (
                <>
                  Show less
                  <ChevronUp className="size-4" />
                </>
              ) : (
                <>
                  View all {knownActors.length} cast members
                  <ChevronDown className="size-4" />
                </>
              )}
            </Button>
          )}
        </section>
      )}

      {crewSections.map((section) => (
        <section key={section.title} aria-label={section.title}>
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
        </section>
      ))}
    </div>
  );
}
