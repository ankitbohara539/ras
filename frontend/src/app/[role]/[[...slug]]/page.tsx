import { notFound } from "next/navigation";
import { RoleWorkspace } from "@/components/dashboard/RoleWorkspace";
import { roles, type Role } from "@/types";

export default async function Page({
  params,
}: {
  params: Promise<{ role: string; slug?: string[] }>;
}) {
  const { role, slug = [] } = await params;
  const normalized = role.toUpperCase() as Role;
  if (!roles.includes(normalized)) notFound();
  return <RoleWorkspace role={normalized} slug={slug} />;
}
