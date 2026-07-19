import { Star, Users, Calendar, Clock } from "lucide-react";
import { cn, formatRating, formatVotes, formatRuntime, formatYear } from "@/lib/utils";
import type { Title } from "@/lib/types";

interface TitleStatsPanelProps {
  title: Title;
  className?: string;
}

interface StatItemProps {
  icon: React.ReactNode;
  label: string;
  value: string;
}

function StatItem({ icon, label, value }: StatItemProps) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border p-3">
      <div className="flex size-8 items-center justify-center rounded-md bg-surface text-muted">
        {icon}
      </div>
      <div className="flex flex-col">
        <span className="text-xs text-muted">{label}</span>
        <span className="text-sm font-medium">{value}</span>
      </div>
    </div>
  );
}

export function TitleStatsPanel({ title, className }: TitleStatsPanelProps) {
  return (
    <div className={cn("grid grid-cols-2 gap-3", className)}>
      <StatItem
        icon={<Star className="size-4" />}
        label="Rating"
        value={formatRating(title.averageRating)}
      />
      <StatItem
        icon={<Users className="size-4" />}
        label="Votes"
        value={formatVotes(title.numVotes)}
      />
      <StatItem
        icon={<Calendar className="size-4" />}
        label="Released"
        value={formatYear(title.startYear, title.endYear)}
      />
      <StatItem
        icon={<Clock className="size-4" />}
        label="Runtime"
        value={formatRuntime(title.runtimeMinutes)}
      />
    </div>
  );
}
