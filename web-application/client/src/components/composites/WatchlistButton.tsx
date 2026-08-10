import { Bookmark, BookmarkCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface WatchlistButtonProps {
  isSaved?: boolean;
  onToggle?: () => void;
  isDisabled?: boolean;
  saveCount?: number;
  showLabel?: boolean;
  className?: string;
}

export function WatchlistButton({
  isSaved = false,
  onToggle,
  isDisabled,
  saveCount,
  showLabel = true,
  className,
}: WatchlistButtonProps) {
  return (
    <Button
      variant="outline"
      onClick={onToggle}
      disabled={isDisabled}
      className={cn(
        "flex items-center gap-2",
        isSaved && "border-accent-green-bg bg-accent-green-bg text-accent-green-text",
        className,
      )}
      aria-label={isSaved ? "Remove from watchlist" : "Add to watchlist"}
      aria-pressed={isSaved}
    >
      {isSaved ? <BookmarkCheck className="size-4" /> : <Bookmark className="size-4" />}
      {showLabel && (
        <span>{isSaved ? "In Watchlist" : "Watchlist"}</span>
      )}
      {saveCount != null && (
        <span className="rounded-full bg-muted px-1.5 text-[11px] text-muted tabular-nums">
          {saveCount}
        </span>
      )}
    </Button>
  );
}