import { ROLE_LABEL, ROLE_SHORT, type Role } from "@/lib/operations";
export function RoleChip({ role }: { role: Role }) {
  return (
    <span className={`role-chip role-chip-${role}`} title={ROLE_LABEL[role]}>
      {ROLE_SHORT[role]}
    </span>
  );
}
