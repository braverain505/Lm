/**
 * Roles allowed to manage school-wide settings (School Settings page, logo,
 * sessions/terms) and the report-card template picker.
 *
 * Deliberately a whitelist — ordinary teaching and staff roles are excluded
 * even if a custom role happens to carry the school.manage permission.
 */
export const SCHOOL_ADMIN_ROLES = ["super_admin", "director", "admin", "principal"];

export function isSchoolAdminRole(roleCode?: string | null): boolean {
  return !!roleCode && SCHOOL_ADMIN_ROLES.includes(roleCode);
}
