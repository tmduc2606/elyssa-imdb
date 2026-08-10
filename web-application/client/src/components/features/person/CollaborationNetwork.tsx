import { Link } from "react-router";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/composites/EmptyState";
import { getInitials } from "@/lib/utils";
import type { Collaborator } from "@/lib/types";

interface CollaborationNetworkProps {
  collaborators: Collaborator[];
  isLoading?: boolean;
}

export function CollaborationNetwork({ collaborators, isLoading }: CollaborationNetworkProps) {
  if (isLoading) {
    return (
      <div className="flex flex-wrap gap-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-32 rounded-lg" />
        ))}
      </div>
    );
  }

  if (collaborators.length === 0) return <EmptyState title="No collaborators" />;

  const sorted = [...collaborators].sort((a, b) => b.collaborationCount - a.collaborationCount);

  return (
    <section>
      <h3 className="mb-4 text-lg font-semibold">Frequent collaborators</h3>
      <div className="flex flex-wrap gap-3">
        {sorted.slice(0, 12).map((collab) => (
          <Link
            key={collab.person.id}
            to={`/person/${collab.person.id}`}
            className="flex items-center gap-2 rounded-lg border border-border p-2 text-sm transition-colors hover:bg-muted"
          >
            <Avatar className="size-8 rounded-full">
              <AvatarImage src={collab.person.posterUrl ?? undefined} alt={collab.person.primaryName ?? "Collaborator"} />
              <AvatarFallback className="text-[10px]">{getInitials(collab.person.primaryName)}</AvatarFallback>
            </Avatar>
            <div className="flex flex-col">
              <span className="truncate max-w-24">{collab.person.primaryName}</span>
              <span className="text-xs text-muted">
                {collab.collaborationCount} title{collab.collaborationCount !== 1 ? "s" : ""}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
