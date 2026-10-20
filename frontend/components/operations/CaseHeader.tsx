"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowLeft } from "@phosphor-icons/react";
import {
  type Brief,
  type Case,
  type TeamMember,
  assignCase,
  can,
  channelName,
  claimCase,
  dateTime,
  explainError,
  human,
  money,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { PageHeading, Status } from "./Primitives";
import { ReportButtons } from "./ReportButtons";
import { RoleChip } from "./RoleChip";
import { useAnalyst } from "./useAnalyst";

export function nameOf(team: TeamMember[] | undefined, username: string) {
  return team?.find((member) => member.username === username)?.display_name ?? username;
}

function OwnerRow({
  item,
  team,
  onChanged,
}: {
  item: Case;
  team?: TeamMember[];
  onChanged: (item: Case) => void;
}) {
  const analyst = useAnalyst();
  const { refresh } = useOperations();
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const owner = item.assignee ? nameOf(team, item.assignee) : null;
  const handled = (item.handled_by ?? []).map((username) => nameOf(team, username));

  async function run(task: () => Promise<Case>) {
    setBusy(true);
    setError("");
    try {
      onChanged(await task());
    } catch (err) {
      setError(explainError(err, team));
    } finally {
      setBusy(false);
      await refresh().catch(() => {});
    }
  }

  return (
    <div className="owner-row">
      <p>
        {owner ? `Assigned to ${owner}` : "Unassigned"}
        {handled.length > 0 && ` · handled by ${handled.join(", ")}`}
      </p>
      {!item.assignee && item.status !== "resolved" && (
        <button
          disabled={busy}
          onClick={() => {
            void run(() => claimCase(item.case_id, item.version));
          }}
        >
          Claim
        </button>
      )}
      {can(analyst?.role, "assign") && team && (
        <span className="reassign">
          <label className="sr-only" htmlFor="reassign-target">
            Reassign to
          </label>
          <select id="reassign-target" value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">Reassign to…</option>
            {team
              .filter((member) => member.username !== item.assignee)
              .map((member) => (
                <option key={member.username} value={member.username}>
                  {member.display_name} · {member.role_label}
                </option>
              ))}
          </select>
          <button
            disabled={busy || !target}
            onClick={() => {
              void run(() => assignCase(item.case_id, target, item.version));
            }}
          >
            Reassign
          </button>
        </span>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
          {error.endsWith("already claimed this case.") && (
            <button
              onClick={() => {
                setError("");
                void refresh().catch(() => {});
              }}
            >
              Refresh
            </button>
          )}
        </p>
      )}
    </div>
  );
}

/** Investigation, verdict, score and protection at a glance. */
export function StateStrip({ item }: { item: Case }) {
  const latestAction = [...item.actions].sort((a, b) => a.created_at.localeCompare(b.created_at)).at(-1);
  return (
    <div className="case-state-strip">
      <div>
        <span>Investigation</span>
        <Status value={item.status} />
      </div>
      <div>
        <span>Analyst verdict</span>
        <Status value={item.verdict} />
      </div>
      <div>
        <span>Detection score</span>
        <strong className={`risk-score ${item.severity}`}>{(item.score * 100).toFixed(1)} / 100</strong>
      </div>
      <div>
        <span>Protection</span>
        <strong>
          {latestAction ? `${human(latestAction.operation)} ${latestAction.status}` : "No action recorded"}
        </strong>
      </div>
    </div>
  );
}

/** Back link, title, priority and ownership at the top of a case. */
export function CaseHeader({
  item,
  brief,
  team,
  onChanged,
}: {
  item: Case;
  brief: Brief | null;
  team?: TeamMember[];
  onChanged: (item: Case) => void;
}) {
  const complaint = item.complaint ? ` · ${item.complaint.complaint_id}` : "";
  return (
    <>
      <div className="case-back">
        <Link href="/cases">
          <ArrowLeft size={12} />
          Investigation queue
        </Link>
        <span>Updated {dateTime(item.updated_at)} IST</span>
      </div>
      <PageHeading
        title={`${brief?.typology ?? channelName(item.channel)} · ${item.case_id}`}
        description={
          [channelName(item.channel), item.account_id, money(item.amount_minor)].join(" · ") + complaint
        }
      >
        <ReportButtons caseId={item.case_id} />
      </PageHeading>
      <div className="case-meta-row">
        <span className="priority-pill" title={item.priority_reason}>
          Priority <strong>{item.priority ?? "—"}</strong>
          {item.priority_reason && <small>{item.priority_reason}</small>}
        </span>
        {brief && (
          <span className="required-role">
            Needs <RoleChip role={brief.required_role} />
          </span>
        )}
      </div>
      <OwnerRow item={item} team={team} onChanged={onChanged} />
    </>
  );
}
