import { useState } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface LoginFormProps {
  onSubmit: (data: { email: string; password: string }) => void;
  isLoading?: boolean;
  error?: string | null;
}

export function LoginForm({ onSubmit, isLoading, error }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <div className="mx-auto flex max-w-sm flex-col items-center px-4 py-24">
      <h1 className="mb-8 text-2xl">Sign in</h1>
      <form
        className="flex w-full flex-col gap-4"
        aria-label="Sign in form"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ email, password });
        }}
      >
        {error && (
          <div
            id="login-error"
            role="alert"
            className="rounded-lg border border-accent-red-bg bg-accent-red-bg px-3 py-2 text-sm text-accent-red-text"
          >
            {error}
          </div>
        )}
        <div>
          <label htmlFor="login-email" className="sr-only">Email</label>
          <Input
            id="login-email"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            aria-describedby={error ? "login-error" : undefined}
            aria-invalid={error ? true : undefined}
            required
          />
        </div>
        <div>
          <label htmlFor="login-password" className="sr-only">Password</label>
          <Input
            id="login-password"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            aria-describedby={error ? "login-error" : undefined}
            aria-invalid={error ? true : undefined}
            required
          />
        </div>
        <Button type="submit" className="w-full" disabled={isLoading}>
          {isLoading ? "Signing in..." : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        No account?{" "}
        <Link to="/auth/register" className="text-foreground underline">
          Register
        </Link>
      </p>
    </div>
  );
}
