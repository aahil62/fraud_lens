import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { Snapshot } from "@/lib/operations";
import { TeamView } from "./TeamView";
const mocks = vi.hoisted(() => ({
  analyst: null as null | { username: string; display_name: string; role: string },
}));
vi.mock("./OperationsProvider", () => ({
  useOperations: () => ({
    refresh: vi.fn(),
    snapshot: {
      team: [
        {
          username: "kmehta",
          display_name: "K. Mehta",
          role: "l1_analyst",
          role_label: "L1 Analyst",
          online: true,
          last_seen: "2026-10-19T01:00:00Z",
          current_case_id: "CASE-1",
          open_assigned: 2,
          resolved_today: 1,
        },
      ],
      approvals: [
        {
          case_id: "CASE-1",
          approval_id: "APR-1",
          action: "confirm_fraud",
          requested_by: "kmehta",
          required_role: "l2_analyst",
          notes: "Mule pattern",
          requested_at: "2026-10-19T01:00:00Z",
        },
      ],
      agent: {
        auto_assign: false,
        briefs_drafted: 7,
        liens_placed: 2,
        cases_auto_assigned: 0,
        cases_triaged: 3,
      },
    } as unknown as Snapshot,
  }),
}));
vi.mock("./useAnalyst", async (original) => ({
  ...(await original<typeof import("./useAnalyst")>()),
  useAnalyst: () => mocks.analyst,
}));
beforeEach(() => {
  mocks.analyst = null;
});
it("shows approvals an L2 can decide but hides the supervisor-only agent policy", () => {
  mocks.analyst = { username: "riyer", display_name: "R. Iyer", role: "l2_analyst" };
  render(<TeamView />);
  expect(screen.getByText("K. Mehta requests: Confirm fraud")).toBeInTheDocument();
  expect(screen.queryByText("Agent policy")).not.toBeInTheDocument();
});
it("gives supervisors the auto-assign switch and real counters", () => {
  mocks.analyst = { username: "asharma", display_name: "A. Sharma", role: "supervisor" };
  render(<TeamView />);
  expect(screen.getByRole("switch", { name: /Auto-assign/ })).not.toBeChecked();
  expect(screen.getByText("Briefs drafted").nextSibling).toHaveTextContent("7");
});
it("does not list the requester's own approval", () => {
  mocks.analyst = { username: "kmehta", display_name: "K. Mehta", role: "l1_analyst" };
  render(<TeamView />);
  expect(screen.getByText("Nothing is waiting for your approval.")).toBeInTheDocument();
});
