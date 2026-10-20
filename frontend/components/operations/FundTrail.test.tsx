import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { TraceHop } from "@/lib/operations";
import { FundTrail } from "./FundTrail";
const hop = (
  n: number,
  account: string,
  traced: number,
  lien: number,
  outcome: TraceHop["outcome"],
): TraceHop => ({
  hop: n,
  account_id: account,
  inbound_txn_ids: [],
  traced_minor: traced,
  available_minor: 0,
  lien_minor: lien,
  outcome,
});
it("renders the victim, every hop, rupee amounts and outcome badges", () => {
  render(
    <FundTrail
      victimAccountId="SIM-VICTIM-1234"
      reportedMinor={4800000}
      trace={[
        hop(1, "SIM-M1-5678", 4800000, 4800000, "held"),
        hop(2, "SIM-M2-9012", 3000000, 1200000, "partially_recovered"),
        hop(2, "SIM-M3-3456", 0, 0, "funds_moved"),
      ]}
    />,
  );
  expect(screen.getByText("Victim")).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
  expect(screen.getAllByText("₹48,000").length).toBeGreaterThan(0);
  expect(screen.getByText("₹12,000")).toBeInTheDocument();
  expect(screen.getByText("Held")).toHaveClass("good");
  expect(screen.getByText("Partially recovered")).toHaveClass("warning");
  expect(screen.getByText("Funds moved")).toHaveClass("bad");
});
it("never offers a per-hop action on the victim's own account", () => {
  render(
    <FundTrail
      victimAccountId="SIM-VICTIM-1234"
      reportedMinor={4800000}
      trace={[
        hop(1, "SIM-M1-5678", 3000000, 0, "funds_moved"),
        hop(2, "SIM-VICTIM-1234", 1800000, 0, "pending"),
      ]}
      renderAction={(item) => <button>Close {item.account_id}</button>}
    />,
  );
  expect(screen.getByRole("button", { name: "Close SIM-M1-5678" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Close SIM-VICTIM-1234" })).toBeNull();
});
