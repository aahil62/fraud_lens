import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { Case } from "@/lib/operations";
import { LedgerView } from "./OperationsViews";
const mocks = vi.hoisted(() => ({ fetch: vi.fn() }));
vi.mock("./OperationsProvider", () => ({
  useOperations: () => ({ snapshot: null, mutate: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("@/lib/operations", async (original) => ({
  ...(await original<typeof import("@/lib/operations")>()),
  opsFetch: mocks.fetch,
}));
const row = (id: string, assignee: string | null, priority: number) =>
  ({
    case_id: id,
    txn_id: id,
    account_id: `acct-${id}`,
    channel: "upi",
    amount_minor: 1000,
    score: 0.8,
    severity: "high",
    status: "new",
    verdict: "unreviewed",
    version: 1,
    created_at: "2026-10-19T00:00:00Z",
    updated_at: "2026-10-19T00:00:00Z",
    assigned_to: assignee ? "K. Mehta" : null,
    assignee,
    priority,
    notes: "",
    signals: [],
    reasons: [],
    related_transactions: [],
    related_accounts: [],
    actions: [],
    timeline: [],
  }) as Case;
it("Unassigned filter asks the API for that view and hides assigned cases", async () => {
  mocks.fetch.mockResolvedValue({
    items: [row("CASE-OWNED", "kmehta", 90), row("CASE-OPEN", null, 40)],
    total: 2,
  });
  render(<LedgerView kind="cases" />);
  expect(await screen.findByText("CASE-OWNED")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Claim CASE-OPEN" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Unassigned/ }));
  await waitFor(() =>
    expect(mocks.fetch).toHaveBeenLastCalledWith(expect.stringContaining("view=unassigned")),
  );
  await waitFor(() => expect(screen.queryByText("CASE-OWNED")).not.toBeInTheDocument());
  expect(screen.getByText("CASE-OPEN")).toBeInTheDocument();
});
