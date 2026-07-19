import { RegisterForm } from "@/components/features/auth/RegisterForm";

export function Register() {
  return (
    <RegisterForm
      onSubmit={(data) => {
        console.log("Register", data);
      }}
    />
  );
}
