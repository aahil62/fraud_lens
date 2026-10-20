import { getToken } from "./auth";
import { ROLE_LABEL } from "./roles";
import type {
  ApprovalAction,
  Brief,
  Case,
  CaseAction,
  Decision,
  Role,
  Snapshot,
  TeamMember,
} from "./ops-types";

export * from "./format";
export * from "./ops-types";
export * from "./roles";

export const OPS_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001") + "/ops";
export class OperationsError extends Error {
  constructor(
    public status: number,
    message: string,
    public data: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "OperationsError";
  }
}
const article = (label: string) => (/^[AEIOUL]/.test(label) ? "an" : "a");
/** Turns role (403) and ownership (409) refusals into the console's copy. */
export function explainError(err: unknown, team: TeamMember[] = [], fallback = "Request failed.") {
  if (err instanceof OperationsError) {
    const role = err.data.required_role as Role | undefined;
    if (err.status === 403 && role && ROLE_LABEL[role])
      return `This needs ${article(ROLE_LABEL[role])} ${ROLE_LABEL[role]}. Request approval instead.`;
    const owner = err.data.assignee as string | undefined;
    if (err.status === 409 && owner) {
      const name = team.find((m) => m.username === owner)?.display_name ?? owner;
      return `${name} already claimed this case.`;
    }
    return err.message;
  }
  return err instanceof Error ? err.message : fallback;
}
export async function opsFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) throw new OperationsError(401, "Your session has ended. Sign in again.");
  const response = await fetch(OPS_BASE + path, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new OperationsError(
      response.status,
      typeof data?.detail === "string" ? data.detail : `Request failed (${response.status}).`,
      data && typeof data === "object" ? data : {},
    );
  }
  return response.json() as Promise<T>;
}
const casePath = (caseId: string, suffix: string) => `/cases/${encodeURIComponent(caseId)}/${suffix}`;
const post = <T>(path: string, body: unknown) =>
  opsFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
export function runCaseAction(
  caseId: string,
  action: CaseAction,
  version: number,
  notes: string,
  extra: { amount_minor?: number | null; target_account_id?: string | null } = {},
) {
  return post<Case>(casePath(caseId, "decision"), {
    action,
    expected_version: version,
    notes: notes.trim(),
    ...(extra.amount_minor ? { amount_minor: extra.amount_minor } : {}),
    ...(extra.target_account_id ? { target_account_id: extra.target_account_id } : {}),
  });
}
/** A verdict or status change; refuses a verdict without notes before calling the API. */
export function decideCase(caseId: string, action: Decision, version: number, notes: string) {
  if ((action === "confirm_fraud" || action === "false_positive") && !notes.trim())
    throw new OperationsError(422, "Add investigation notes before recording a verdict.");
  return runCaseAction(caseId, action, version, notes);
}
export const claimCase = (caseId: string, version: number) =>
  post<Case>(casePath(caseId, "claim"), { expected_version: version });
export const assignCase = (caseId: string, username: string, version: number) =>
  post<Case>(casePath(caseId, "assign"), {
    username,
    expected_version: version,
  });
export const requestApproval = (
  caseId: string,
  action: ApprovalAction,
  version: number,
  notes: string,
  targetAccountId?: string | null,
) =>
  post<Case>(casePath(caseId, "approval-request"), {
    action,
    expected_version: version,
    notes: notes.trim(),
    ...(targetAccountId ? { target_account_id: targetAccountId } : {}),
  });
export const decideApproval = (caseId: string, approve: boolean, notes = "") =>
  post<Case>(casePath(caseId, "approval"), { approve, notes: notes.trim() });
export const heartbeat = (currentCaseId: string | null) =>
  post<{ ok: true }>("/presence/heartbeat", { current_case_id: currentCaseId });
export const fileComplaint = (complaint: {
  complaint_id: string;
  source: "1930_helpline" | "ncrp_portal" | "branch";
  victim_account_id: string;
  reported_txn_id: string;
  reported_at: string;
}) => post<Case>("/complaints", complaint);
export const setAgentSettings = (autoAssign: boolean) =>
  post<{ auto_assign: boolean }>("/agent/settings", {
    auto_assign: autoAssign,
  });
export const getBrief = (caseId: string) => opsFetch<Brief>(casePath(caseId, "brief"));
export async function exportReport(caseId: string, format: "json" | "markdown" | "pdf") {
  const token = getToken();
  if (!token) throw new OperationsError(401, "Sign in again to export a report.");
  const response = await fetch(`${OPS_BASE}/cases/${encodeURIComponent(caseId)}/report?format=${format}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new OperationsError(response.status, "Report export failed. Try again.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${caseId}.${format === "markdown" ? "md" : format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function newestSnapshot(current: Snapshot | null, incoming: Snapshot): Snapshot {
  return current && current.cursor > incoming.cursor ? current : incoming;
}
