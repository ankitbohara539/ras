import type { Role } from "@/types";

const priority: Role[] = ["ADMIN", "AUTHORITY", "RESPONDER", "CITIZEN"];

export function primaryRole(roles: Role[]): Role {
  return priority.find((role) => roles.includes(role)) ?? "CITIZEN";
}

export function rolePath(role: Role): string {
  return "/" + role.toLowerCase();
}
