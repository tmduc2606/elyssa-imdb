import { AlertCircle } from "lucide-react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

interface ErrorFallbackProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorFallback({
  title = "Something went wrong",
  message = "An unexpected error occurred. Please try again.",
  onRetry,
}: ErrorFallbackProps) {
  return (
    <div className="flex items-center justify-center p-8">
      <Alert variant="default" className="max-w-md">
        <AlertCircle className="size-5" />
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription className="mt-2 flex flex-col gap-4">
          <p>{message}</p>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry} className="self-start">
              Try again
            </Button>
          )}
        </AlertDescription>
      </Alert>
    </div>
  );
}
