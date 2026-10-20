import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { type Brief, type Case, OperationsError } from "@/lib/operations";
import CaseWorkspace from "./CaseWorkspace";
const item = {
  case_id: "CASE-7",
  txn_id: "TX-7",
  account_id: "SIM-ACC-7",
  channel: "upi",
  amount_minor: 4800000,
  score: 0.9,
  severity: "critical",
  status: "investigating",
  verdict: "unreviewed",
  version: 3,
  created_at: "2026-10-20T10:00:00+00:00",
  updated_at: "2026-10-20T10:00:00+00:00",
  assigned_to: null,
  notes: "",
  signals: [],
  reasons: [],
  related_transactions: [],
  related_accounts: [],
  actions: [],
  timeline: [],
} as Case;
const brief = {
  typology: "Mule pass-through",
  summary: "Summary",
  evidence: [],
  recommended_action: "confirm_fraud",
  target_account_id: null,
  amount_minor: null,
  required_role: "l2_analyst",
  required_role_label: "L2 Senior Analyst",
  confidence: "high",
  next_steps: [],
  ncrp_narrative: "",
  generated_by: "template",
} as Brief;
const mocks = vi.hoisted(() => ({ requestApproval: vi.fn(), opsFetch: vi.fn(), getBrief: vi.fn() }));
vi.mock("./OperationsProvider", () => ({
  useOperations: () => ({
    snapshot: { cursor: 1, team: [] },
    refresh: vi.fn().mockResolvedValue(undefined),
    setCurrentCase: vi.fn(),
  }),
}));
vi.mock("./useAnalyst", () => ({
  useAnalyst: () => ({ username: "kmehta", display_name: "K. Mehta", role: "l1_analyst" }),
  initials: () => "KM",
}));
vi.mock("@/lib/operations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/operations")>()),
  opsFetch: mocks.opsFetch,
  getBrief: mocks.getBrief,
  requestApproval: mocks.requestApproval,
}));
it("keeps the approval request and its notes open when the request fails", async () => {
  mocks.opsFetch.mockResolvedValue(item);
  mocks.getBrief.mockResolvedValue(brief);
  mocks.requestApproval.mockRejectedValue(new OperationsError(409, "Case changed since you opened it."));
  render(<CaseWorkspace caseId="CASE-7" />);
  fireEvent.click(await screen.findByRole("button", { name: "Request approval from L2" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Why should this happen?" }), {
    target: { value: "Funds left within minutes" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send request to L2" }));
  expect(await screen.findByText("Case changed since you opened it.")).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Why should this happen?" })).toHaveValue(
    "Funds left within minutes",
  );
});
