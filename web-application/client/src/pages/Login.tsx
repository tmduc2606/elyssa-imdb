import { LoginForm } from "@/components/features/auth/LoginForm";

export function Login() {
  return (
    <LoginForm
      onSubmit={(data) => {
        console.log("Login", data);
      }}
    />
  );
}
