import { PageHeader } from "@/components/composites/PageHeader";
import { ProfileForm } from "@/components/features/account/ProfileForm";
import { Settings } from "@/components/features/account/Settings";
import type { User } from "@/lib/types";

const placeholderUser: User = {
  id: "",
  email: "user@example.com",
  displayName: "User",
};

export function Account() {
  const user = placeholderUser;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <PageHeader title="Account" />
      <div className="mt-8 flex flex-col gap-12">
        <section>
          <h2 className="mb-4 text-lg font-semibold">Profile</h2>
          <ProfileForm
            user={user}
            onSubmit={() => {}}
          />
        </section>
        <section>
          <Settings />
        </section>
      </div>
    </div>
  );
}
