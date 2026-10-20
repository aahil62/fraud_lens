const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";
export const TYPOLOGIES = ["mule_layering", "sim_swap_takeover", "card_testing", "atm_cashout"] as const;
export type Typology = (typeof TYPOLOGIES)[number];
export type AttackStep = { label: string; status: "pending" | "done" | "blocked"; at: string | null };
export type AttackStatus = {
  attack_id: string;
  typology: Typology;
  steps: AttackStep[];
  outcome: "in_progress" | "caught" | "partially_caught" | "missed";
  case_id_masked: string | null;
  complaint_id: string | null;
  traced_total_minor: number;
  held_total_minor: number;
};
export class AttackError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "AttackError";
  }
}
async function call<T>(path: string, method: "GET" | "POST" = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/public${path}`, {
      method,
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new AttackError(0, "The demo server is unreachable. Try again shortly.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new AttackError(
      response.status,
      typeof data?.detail === "string" ? data.detail : `Request failed (${response.status}).`,
    );
  return data as T;
}
export const launchAttack = (typology: Typology, victimAmountMinor: number) =>
  call<{ attack_id: string; status_url: string }>("/attacks", "POST", {
    typology,
    victim_amount_minor: victimAmountMinor,
  });
export const getAttack = (attackId: string) => call<AttackStatus>(`/attacks/${encodeURIComponent(attackId)}`);
export const reportTo1930 = (attackId: string) =>
  call<AttackStatus>(`/attacks/${encodeURIComponent(attackId)}/report-1930`, "POST");
