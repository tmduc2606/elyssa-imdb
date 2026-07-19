import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface RatingBadgeProps {
  rating: number | null | undefined;
  size?: "sm" | "md";
  className?: string;
}

function getRatingColor(rating: number | null | undefined) {
  if (rating == null) return "bg-accent-yellow-bg text-accent-yellow-text";
  if (rating >= 8) return "bg-accent-green-bg text-accent-green-text";
  if (rating >= 6) return "bg-accent-yellow-bg text-accent-yellow-text";
  return "bg-accent-red-bg text-accent-red-text";
}

export function RatingBadge({ rating, size = "sm", className }: RatingBadgeProps) {
  if (rating == null) return null;

  return (
    <span
      aria-label={`Rating: ${rating.toFixed(1)} out of 10`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium leading-none",
        size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-1 text-xs",
        getRatingColor(rating),
        className,
      )}
    >
      <Star className={cn("fill-current", size === "sm" ? "size-2.5" : "size-3")} aria-hidden="true" />
      {rating.toFixed(1)}
    </span>
  );
}
