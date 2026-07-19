import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface FilterChip {
  label: string;
  value: string;
}

interface FilterBarProps {
  chips: FilterChip[];
  selected: string[];
  onChange: (selected: string[]) => void;
  className?: string;
}

export function FilterBar({ chips, selected, onChange, className }: FilterBarProps) {
  return (
    <div className={cn("flex flex-wrap gap-2", className)} role="group" aria-label="Filters">
      {chips.map((chip) => {
        const isActive = selected.includes(chip.value);
        return (
          <Button
            key={chip.value}
            variant={isActive ? "default" : "outline"}
            size="sm"
            className="rounded-full text-xs"
            aria-pressed={isActive}
            onClick={() => {
              onChange(
                isActive
                  ? selected.filter((v) => v !== chip.value)
                  : [...selected, chip.value],
              );
            }}
          >
            {chip.label}
            {isActive && <X className="size-3" />}
          </Button>
        );
      })}
      {selected.length > 0 && (
        <Button
          variant="ghost"
          size="xs"
          onClick={() => onChange([])}
          className="text-xs text-muted"
        >
          Clear all
        </Button>
      )}
    </div>
  );
}
