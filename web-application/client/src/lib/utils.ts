import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ROLE_LABELS } from "./constants";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRating(rating: number | null | undefined): string {
  if (rating == null) return "—";
  return rating.toFixed(1);
}

export function formatVotes(votes: number | null | undefined): string {
  if (votes == null) return "—";
  if (votes >= 1_000_000) return `${(votes / 1_000_000).toFixed(1)}M`;
  if (votes >= 1_000) return `${(votes / 1_000).toFixed(1)}K`;
  return votes.toLocaleString();
}

export function formatRuntime(minutes: number | null | undefined): string {
  if (minutes == null) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function formatYear(start: number | null | undefined, end?: number | null | undefined): string {
  if (start == null) return "—";
  if (end == null) return String(start);
  return `${start}–${end}`;
}

export function getInitials(name: string | null | undefined): string {
  if (!name) return "";
  return name
    .split(" ")
    .map((n) => n[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function formatRole(
  category: string | null | undefined,
  job: string | null | undefined,
  character?: string | null,
): string {
  if (character) return character;
  const key = job ?? category;
  if (!key) return "";
  return ROLE_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
