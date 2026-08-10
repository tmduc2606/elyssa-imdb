import { useState } from "react";
import { PageHeader } from "@/components/composites/PageHeader";
import { ProfileForm } from "@/components/features/account/ProfileForm";
import { Settings } from "@/components/features/account/Settings";
import { useAuth } from "@/hooks/useAuth";
import { authApiFetch } from "@/lib/authApi";
import { toast } from "sonner";

export function Account() {
  const { user, refreshUser } = useAuth();
  const [saving, setSaving] = useState(false);

  if (!user) return null;

  const handleSave = async (data: { displayName: string }) => {
    setSaving(true);
    try {
      await authApiFetch("/me", {
        method: "PATCH",
        body: JSON.stringify({ displayName: data.displayName }),
      });
      await refreshUser();
      toast.success("Profile updated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <PageHeader title="Account" />
      <div className="mt-8 grid grid-cols-1 gap-10 lg:grid-cols-2">
        <section>
          <h2 className="mb-4 text-lg font-semibold">Profile</h2>
          <ProfileForm
            user={user}
            onSubmit={handleSave}
            isLoading={saving}
          />
        </section>
        <section>
          <Settings />
        </section>
      </div>
    </div>
  );
}