import type { TeamMember } from "@/lib/operations";
import { initials } from "./useAnalyst";
export function TeamPresence({ team, max = 5 }: { team: TeamMember[]; max?: number }) {
  const online = team.filter((member) => member.online);
  if (!online.length) return null;
  const overflow = online.length - max;
  return (
    <ul className="team-presence" aria-label={`${online.length} analysts online`}>
      {online.slice(0, max).map((member) => {
        const onCase = member.current_case_id ? ` · on ${member.current_case_id}` : "";
        const label = `${member.display_name} · ${member.role_label}${onCase}`;
        return (
          <li key={member.username} title={label}>
            <span className="presence-avatar" aria-label={label}>
              {initials(member.display_name)}
            </span>
          </li>
        );
      })}
      {overflow > 0 && (
        <li
          className="presence-overflow"
          title={online
            .slice(max)
            .map((m) => m.display_name)
            .join(", ")}
        >
          +{overflow}
        </li>
      )}
    </ul>
  );
}
