// frontend/src/lib/nail-auth.ts
/**
 * NailFlow client-side role utilities.
 * Reads nail_role from the AuthContext user object.
 */

export type NailRole = "user" | "ops" | "dev";

const ROLE_LEVELS: Record<NailRole, number> = {
  user: 1,
  ops: 2,
  dev: 3,
};

/**
 * Check if a given role has access to the required minimum role.
 * dev >= ops >= user
 */
export function canAccess(userRole: NailRole, required: NailRole): boolean {
  return (ROLE_LEVELS[userRole] ?? 0) >= (ROLE_LEVELS[required] ?? 0);
}

/**
 * Get display name for nail role.
 */
export function getRoleDisplayName(role: NailRole): string {
  const names: Record<NailRole, string> = {
    user: "用户端",
    ops: "运营端",
    dev: "开发端",
  };
  return names[role] ?? "用户端";
}
