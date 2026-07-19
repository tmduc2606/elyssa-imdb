import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  className?: string;
  children?: React.ReactNode;
}

export function PageHeader({ title, description, className, children }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
      {description && <p className="text-muted">{description}</p>}
      {children}
    </div>
  );
}
