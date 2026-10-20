"use client";
import Link from "next/link";
import { useState } from "react";
import { Robot } from "@phosphor-icons/react";
import {
  ACTION_LABEL,
  can,
  dateTime,
  decidableApprovals,
  explainError,
  setAgentSettings,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { Empty, Loading, PageHeading } from "./Primitives";
import { RoleChip } from "./RoleChip";
import { initials, useAnalyst } from "./useAnalyst";
import "@/app/workspace-views.css";
export function TeamView() {
  const { snapshot, refresh } = useOperations();
  const analyst = useAnalyst();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!snapshot) return <Loading />;
  const team = snapshot.team ?? [];
  const waiting = decidableApprovals(snapshot, analyst);
  const agent = snapshot.agent;
  const nameOf = (username: string) => team.find((m) => m.username === username)?.display_name ?? username;
  async function toggle(enabled: boolean) {
    setBusy(true);
    setError("");
    try {
      await setAgentSettings(enabled);
    } catch (err) {
      setError(explainError(err, team));
    } finally {
      setBusy(false);
      await refresh().catch(() => {});
    }
  }
  return (
    <div className="workspace-view team-view">
      <PageHeading
        title="Team & approvals"
        description="Who is online, who owns what, and which decisions are waiting for a senior analyst."
      />
      <section className="ops-section">
        <div className="section-heading">
          <div>
            <h2>Analysts</h2>
            <p>Online means a heartbeat in the last 45 seconds.</p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Analyst</th>
                <th>Role</th>
                <th>Status</th>
                <th>Current case</th>
                <th>Open assigned</th>
                <th>Resolved today</th>
              </tr>
            </thead>
            <tbody>
              {team.map((m) => (
                <tr key={m.username}>
                  <td>
                    <span className="owner-cell">
                      <span className="presence-avatar small" aria-hidden="true">
                        {initials(m.display_name)}
                      </span>
                      {m.display_name}
                    </span>
                  </td>
                  <td>
                    <RoleChip role={m.role} />
                  </td>
                  <td>
                    <span className={`presence-state ${m.online ? "online" : ""}`}>
                      {m.online ? "Online" : m.last_seen ? `Last seen ${dateTime(m.last_seen)}` : "Offline"}
                    </span>
                  </td>
                  <td>
                    {m.current_case_id ? (
                      <Link
                        className="record-link"
                        href={`/case?case_id=${encodeURIComponent(m.current_case_id)}`}
                      >
                        {m.current_case_id}
                      </Link>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="numeric">{m.open_assigned}</td>
                  <td className="numeric">{m.resolved_today}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!team.length && <Empty>No analysts have signed in yet.</Empty>}
      </section>
      <section className="ops-section">
        <div className="section-heading">
          <div>
            <h2>Approvals waiting for you</h2>
            <p>Requests your role can decide. You cannot approve your own.</p>
          </div>
        </div>
        {waiting.length ? (
          <ul className="approval-list">
            {waiting.map((a) => (
              <li key={a.approval_id}>
                <span>
                  <strong>
                    {nameOf(a.requested_by)} requests: {ACTION_LABEL[a.action]}
                  </strong>
                  <small>{a.notes}</small>
                </span>
                <RoleChip role={a.required_role} />
                <Link className="primary-button" href={`/case?case_id=${encodeURIComponent(a.case_id)}`}>
                  Review {a.case_id}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>Nothing is waiting for your approval.</Empty>
        )}
      </section>
      {analyst?.role === "supervisor" && agent && (
        <section className="ops-section agent-policy" aria-labelledby="agent-policy-heading">
          <div className="section-heading">
            <div>
              <h2 id="agent-policy-heading">
                <Robot size={17} weight="duotone" aria-hidden="true" /> Agent policy
              </h2>
              <p>
                The agent triages, drafts and places golden-hour liens. It never confirms fraud, releases
                funds or closes accounts.
              </p>
            </div>
          </div>
          <label className="switch-row">
            <input
              type="checkbox"
              role="switch"
              checked={agent.auto_assign}
              disabled={busy || !can(analyst.role, "agent_settings")}
              onChange={(e) => {
                void toggle(e.target.checked);
              }}
            />
            <span>
              <strong>Auto-assign</strong>
              <small>Assign unassigned cases by priority to online L1 analysts with the lightest load.</small>
            </span>
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <dl className="agent-counters">
            {(
              [
                ["Briefs drafted", agent.briefs_drafted],
                ["Liens placed", agent.liens_placed],
                ["Cases auto-assigned", agent.cases_auto_assigned],
                ["Cases triaged", agent.cases_triaged],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value.toLocaleString("en-IN")}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </div>
  );
}
