import { Link } from "react-router";
import { User } from "lucide-react";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { cn, getInitials } from "@/lib/utils";

interface EntityLinkProps {
  id: string;
  name: string | null;
  type: "title" | "person";
  posterUrl?: string | null;
  className?: string;
  placeholder?: string;
}

export function EntityLink({ id, name, type, posterUrl, className, placeholder }: EntityLinkProps) {
  const to = type === "title" ? `/title/${id}` : `/person/${id}`;
  const isRound = type === "person";
  const isUnknown = !name || name.trim() === "";

  return (
    <Link
      to={to}
      className={cn(
        "group flex items-center gap-2 text-sm transition-colors hover:text-foreground",
        className,
      )}
      aria-label={isUnknown ? "Person details coming soon" : name ?? undefined}
    >
      <Avatar className={cn(isRound ? "size-8 rounded-full" : "size-8 rounded")}>
        {isUnknown ? (
          <AvatarFallback className="bg-muted text-muted">
            <User className="size-4" />
          </AvatarFallback>
        ) : (
          <>
            <AvatarImage src={posterUrl ?? undefined} alt={name ?? ""} />
            <AvatarFallback className="text-[10px]">{getInitials(name)}</AvatarFallback>
          </>
        )}
      </Avatar>
      {isUnknown ? (
        <span className="truncate text-muted italic">
          {placeholder ?? "Details coming soon"}
        </span>
      ) : (
        <span className="truncate text-muted group-hover:text-foreground">{name}</span>
      )}
    </Link>
  );
}