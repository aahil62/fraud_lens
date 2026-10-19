import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { type Case, type Snapshot, type Transaction } from "@/lib/operations";
import { AuditView, DashboardView, ReportsView } from "./OperationsViews";
const mocks = vi.hoisted(() => ({ snapshot: null as Snapshot | null }));
vi.mock("./OperationsProvider", () => ({ useOperations: () => ({ snapshot: mocks.snapshot }) }));
function fixtureCase(id: string, account: string, verdict: string, channel: Case["channel"]): Case {
  return { case_id: id, txn_id: `txn-${id}`, account_id: account, channel, verdict, version: 1, amount_minor: 1000, score: .8, severity: "high", status: "new", created_at: "2026-10-17T12:00:00Z", updated_at: "2026-10-17T12:00:00Z", assigned_to: null, notes: "", signals: [], reasons: [], related_transactions: [], related_accounts: [], actions: [], timeline: [] };
}
function fixtureTransaction(timestamp: string): Transaction {
  return { txn_id: timestamp, account_id: "acct-1", channel: "upi", amount_minor: 1000, timestamp, instrument_id: null, beneficiary_id: null, merchant_id: "merchant", device_id: "device", ip_address: "127.0.0.1", location: "Pune", new_device: false, new_beneficiary: false, failed_auth_attempts: 0, score: 0, payment_status: "posted", bank_reason: null, case_id: null };
}
const cases = [fixtureCase("case-alpha", "acct-1", "fraud", "upi"), fixtureCase("case-beta", "acct-2", "false_positive", "card")];
beforeEach(() => {
  mocks.snapshot = {
    cursor: 1, simulation: true, as_of: "2026-10-17T12:00:00Z", cases, events: [
      { id: 1, event_type: "case_created", actor: "analyst-a", message: "Opened case", case_id: "case-alpha", txn_id: null, metadata: {}, occurred_at: "2026-10-17T12:00:00Z" },
      { id: 2, event_type: "payment_posted", actor: "simulator", message: "Payment posted", case_id: null, txn_id: null, metadata: {}, occurred_at: "2026-10-17T12:00:00Z" },
    ],
    counts: { transactions: 0, pending_payments: 0, posted: 0, declined: 0, cases: 2, pending_review: 2, investigating: 0, escalated: 0, resolved: 0, confirmed_fraud: 0, false_positives: 0, restricted_accounts: 0, restricted_cards: 0, pending_actions: 0, failed_actions: 0 },
    channels: [], transactions: [], actions: [], bank: { connected: true, mode: "normal", accounts: [], last_error: null }, simulation_state: { running: false, interval_seconds: 5 }, detection: { version: "test", coverage: [] },
  };
});
it("combines case-library search and verdict filters without losing export actions", () => {
  render(<ReportsView />);
  fireEvent.change(screen.getByRole("textbox", { name: /search recent case records/i }), { target: { value: "acct-2" } });
  expect(screen.getByRole("link", { name: "case-beta" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "case-alpha" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download PDF report for case-beta" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Verdict" }), { target: { value: "fraud" } });
  expect(screen.getByText(/No recent case records match/)).toBeInTheDocument();
});
it("combines audit text and event-type filters", () => {
  render(<AuditView />);
  fireEvent.change(screen.getByRole("combobox", { name: "Event type" }), { target: { value: "case_created" } });
  expect(screen.getByText("Opened case")).toBeInTheDocument();
  expect(screen.queryByText("Payment posted")).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Search recent events" }), { target: { value: "simulator" } });
  expect(screen.getByText(/No events match these filters/)).toBeInTheDocument();
});
it("bins only snapshot transactions inside the stated thirty-minute window", () => {
  mocks.snapshot = {
    ...mocks.snapshot!, cases: [], counts: { transactions: 5, pending_payments: 1, cases: 0, posted: 3, declined: 1, pending_review: 0, investigating: 0, escalated: 0, resolved: 0, confirmed_fraud: 0, false_positives: 0, restricted_accounts: 0, restricted_cards: 0, pending_actions: 0, failed_actions: 0 },
    channels: [{ channel: "upi", transactions: 5, cases: 0, declined: 1, pending_review: 0, confirmed_fraud: 0, resolved: 0 }],
    transactions: ["2026-10-17T11:29:59Z", "2026-10-17T11:30:01Z", "2026-10-17T11:59:59Z", "2026-10-17T12:01:00Z"].map(fixtureTransaction),
  };
  render(<DashboardView />);
  const activity = screen.getByRole("img", { name: /17:00 to 17:05: 1 attempts/ });
  expect(activity).toHaveAccessibleName(/17:25 to 17:30: 1 attempts/);
  expect(screen.getByText("sampled attempts")).toHaveTextContent("2 sampled attempts");
  expect(screen.getByRole("img", { name: "UPI: 5 payment attempts" })).toBeInTheDocument();
});
it("groups regulatory requirements by issuer and flags unverified ones", async () => {
  const { GuidanceView } = await import("./OperationsViews");
  const ops = await import("@/lib/operations");
  const row = (issuer: string, source: string, url: string | null, status: string) => ({ issuer, source, url, date: "2024-08-06", status,
    what_it_requires: "x", how_fraudlens_models_it: "y", not_covered: "z" });
  vi.spyOn(ops, "opsFetch").mockResolvedValue({ references: [], disclaimer: "d", requirements: [
    row("I4C (Ministry of Home Affairs)", "CFCFRMS and 1930", "https://www.pib.gov.in/x", "Verified"),
    row("NPCI", "UPI hold on disputed amount", null, "modelled on (unverified)") ] });
  render(<GuidanceView />);
  expect(await screen.findByRole("heading", { name: "I4C (Ministry of Home Affairs)" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "NPCI" })).toBeInTheDocument();
  expect(screen.getByText(/modelled on \(unverified\)/)).toBeInTheDocument();
});
it("orders Next to investigate by agent priority, not raw score", () => {
  mocks.snapshot = { ...mocks.snapshot!, cases: [
    { ...fixtureCase("case-high-score", "acct-1", "unreviewed", "upi"), score: .95, priority: 52 },
    { ...fixtureCase("case-complaint", "acct-2", "unreviewed", "upi"), score: .2, priority: 71 },
  ] };
  render(<DashboardView />);
  const ids = screen.getAllByText(/^case-(high-score|complaint)$/).map((node) => node.textContent);
  expect(ids).toEqual(["case-complaint", "case-high-score"]);
});
