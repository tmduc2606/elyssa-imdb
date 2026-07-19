import { useState } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface RegisterFormProps {
  onSubmit: (data: { email: string; password: string; displayName: string }) => void;
  isLoading?: boolean;
  error?: string | null;
}

export function RegisterForm({ onSubmit, isLoading, error }: RegisterFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  return (
    <div className="mx-auto flex max-w-sm flex-col items-center px-4 py-24">
      <h1 className="mb-8 text-2xl">Create account</h1>
      <form
        className="flex w-full flex-col gap-4"
        aria-label="Registration form"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ email, password, displayName });
        }}
      >
        {error && (
          <div
            id="register-error"
            role="alert"
            className="rounded-lg border border-accent-red-bg bg-accent-red-bg px-3 py-2 text-sm text-accent-red-text"
          >
            {error}
          </div>
        )}
        <div>
          <label htmlFor="register-email" className="sr-only">Email</label>
          <Input
            id="register-email"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            aria-describedby={error ? "register-error" : undefined}
            aria-invalid={error ? true : undefined}
            required
          />
        </div>
        <div>
          <label htmlFor="register-name" className="sr-only">Display name</label>
          <Input
            id="register-name"
            placeholder="Display name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="name"
            aria-describedby={error ? "register-error" : undefined}
            aria-invalid={error ? true : undefined}
            required
          />
        </div>
        <div>
          <label htmlFor="register-password" className="sr-only">Password</label>
          <Input
            id="register-password"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            aria-describedby={error ? "register-error" : undefined}
            aria-invalid={error ? true : undefined}
            required
          />
        </div>
        <Button type="submit" className="w-full" disabled={isLoading}>
          {isLoading ? "Registering..." : "Register"}
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        Already have an account?{" "}
        <Link to="/auth/login" className="text-foreground underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
