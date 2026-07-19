import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export function Settings() {
  const [darkMode, setDarkMode] = useState(false);

  return (
    <div className="flex max-w-md flex-col gap-4">
      <h3 className="text-lg font-semibold">Preferences</h3>
      <Separator />
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Dark mode</p>
          <p className="text-xs text-muted">Coming soon</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled
          onClick={() => setDarkMode(!darkMode)}
        >
          {darkMode ? "On" : "Off"}
        </Button>
      </div>
      <Separator />
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Delete account</p>
          <p className="text-xs text-muted">Permanently remove your account and data</p>
        </div>
        <Button variant="outline" size="sm" disabled className="text-accent-red-text">
          Delete
        </Button>
      </div>
    </div>
  );
}
