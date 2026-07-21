import { useState } from "react";
import { useNavigate, Navigate } from "react-router";
import { RegisterForm } from "@/components/features/auth/RegisterForm";
import { useAuth } from "@/hooks/useAuth";

export function Register() {
  const navigate = useNavigate();
  const { register, isLoading, isAuthenticated } = useAuth();
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <RegisterForm
      isLoading={isLoading}
      error={error}
      onSubmit={async (data) => {
        setError(null);
        try {
          await register(data.email, data.password, data.displayName);
          navigate("/", { replace: true });
        } catch (err) {
          setError(err instanceof Error ? err.message : "Registration failed");
        }
      }}
    />
  );
}
