import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { User } from "@/lib/types";

interface ProfileFormProps {
  user: User;
  onSubmit: (data: { displayName: string }) => void;
  isLoading?: boolean;
}

export function ProfileForm({ user, onSubmit, isLoading }: ProfileFormProps) {
  const [displayName, setDisplayName] = useState(user.displayName);

  return (
    <form
      className="flex max-w-md flex-col gap-4"
      aria-label="Profile settings"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ displayName });
      }}
    >
      <div>
        <label htmlFor="profile-email" className="mb-1 block text-sm text-muted">Email</label>
        <Input id="profile-email" value={user.email} disabled />
      </div>
      <div>
        <label htmlFor="profile-name" className="mb-1 block text-sm text-muted">Display name</label>
        <Input
          id="profile-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          autoComplete="name"
          required
        />
      </div>
      <Button type="submit" className="self-start" disabled={isLoading}>
        {isLoading ? "Saving..." : "Save changes"}
      </Button>
    </form>
  );
}
