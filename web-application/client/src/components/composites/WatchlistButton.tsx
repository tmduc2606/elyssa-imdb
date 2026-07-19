import { Bookmark, BookmarkCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface WatchlistButtonProps {
  isSaved?: boolean;
  onToggle?: () => void;
  className?: string;
}

export function WatchlistButton({
  isSaved = false,
  onToggle,
  className,
}: WatchlistButtonProps) {
  return (
    <Button
      variant="outline"
      size="icon"
      onClick={onToggle}
      className={cn(
        isSaved && "border-accent-green-bg bg-accent-green-bg text-accent-green-text",
        className,
      )}
      aria-label={isSaved ? "Remove from watchlist" : "Add to watchlist"}
    >
      {isSaved ? <BookmarkCheck className="size-4" /> : <Bookmark className="size-4" />}
    </Button>
  );
}
