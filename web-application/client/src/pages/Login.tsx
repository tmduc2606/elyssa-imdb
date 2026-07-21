import { useState } from "react";
import { useNavigate, Navigate } from "react-router";
import { LoginForm } from "@/components/features/auth/LoginForm";
import { useAuth } from "@/hooks/useAuth";

export function Login() {
  const navigate = useNavigate();
  const { login, isLoading, isAuthenticated } = useAuth();
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <LoginForm
      isLoading={isLoading}
      error={error}
      onSubmit={async (data) => {
        setError(null);
        try {
          await login(data.email, data.password);
          navigate("/", { replace: true });
        } catch (err) {
          setError(err instanceof Error ? err.message : "Login failed");
        }
      }}
    />
  );
}
