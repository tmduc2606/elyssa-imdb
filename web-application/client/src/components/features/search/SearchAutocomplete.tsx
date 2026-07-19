import { useState, useRef, useEffect, useCallback } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface SearchAutocompleteProps {
  onSearch: (query: string) => void;
  className?: string;
}

export function SearchAutocomplete({ onSearch, className }: SearchAutocompleteProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (trimmed) onSearch(trimmed);
    },
    [query, onSearch],
  );

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <form role="search" onSubmit={handleSubmit} className={cn("relative", className)}>
      <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
      <Input
        ref={inputRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search titles, people..."
        className="h-10 pl-9 text-base"
      />
    </form>
  );
}
