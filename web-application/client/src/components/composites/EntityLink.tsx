import { Link } from "react-router";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { cn, getInitials } from "@/lib/utils";

interface EntityLinkProps {
  id: string;
  name: string;
  type: "title" | "person";
  posterUrl?: string | null;
  className?: string;
}

export function EntityLink({ id, name, type, posterUrl, className }: EntityLinkProps) {
  const to = type === "title" ? `/title/${id}` : `/person/${id}`;
  const isRound = type === "person";

  return (
    <Link
      to={to}
      className={cn(
        "group flex items-center gap-2 text-sm transition-colors hover:text-foreground",
        className,
      )}
    >
      <Avatar className={cn(isRound ? "size-8 rounded-full" : "size-8 rounded")}>
        <AvatarImage src={posterUrl ?? undefined} alt={name} />
        <AvatarFallback className="text-[10px]">{getInitials(name)}</AvatarFallback>
      </Avatar>
      <span className="truncate text-muted group-hover:text-foreground">{name}</span>
    </Link>
  );
}
