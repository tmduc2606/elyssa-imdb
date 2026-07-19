import { Empty, EmptyTitle, EmptyDescription } from "@/components/ui/empty";

interface EmptyStateProps {
  title?: string;
  description?: string;
  children?: React.ReactNode;
}

export function EmptyState({
  title = "Nothing here yet",
  description,
  children,
}: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center p-8">
      <Empty>
        <EmptyTitle>{title}</EmptyTitle>
        {description && <EmptyDescription>{description}</EmptyDescription>}
        {children}
      </Empty>
    </div>
  );
}
