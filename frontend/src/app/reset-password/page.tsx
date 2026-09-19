import { ResetPasswordForm } from "@/features/auth/AuthForms";
export default async function Page({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  return <ResetPasswordForm token={(await searchParams).token} />;
}
