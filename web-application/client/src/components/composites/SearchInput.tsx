import { useState, useCallback } from "react";
import { useNavigate } from "react-router";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface SearchInputProps {
  defaultValue?: string;
  placeholder?: string;
  className?: string;
}

export function SearchInput({
  defaultValue = "",
  placeholder = "Search titles, people...",
  className,
}: SearchInputProps) {
  const [query, setQuery] = useState(defaultValue);
  const navigate = useNavigate();

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (trimmed) {
        navigate(`/search?q=${encodeURIComponent(trimmed)}`);
      }
    },
    [query, navigate],
  );

  return (
    <form role="search" onSubmit={handleSubmit} aria-label="Search" className={cn("relative", className)}>
      <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full pl-8"
      />
    </form>
  );
}
