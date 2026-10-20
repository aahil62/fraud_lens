import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { Brief } from "@/lib/operations";
import { AgentBrief } from "./AgentBrief";
const brief: Brief = {
  typology: "Mule pass-through",
  summary: "Mule pass-through signals on a UPI payment.",
  evidence: ["Pass-through: received ₹48,000"],
  recommended_action: "restrict",
  target_account_id: null,
  amount_minor: null,
  required_role: "l2_analyst",
  required_role_label: "L2 Senior Analyst",
  confidence: "high",
  next_steps: ["Review evidence"],
  ncrp_narrative: "On 19 Oct 2026 IST…",
  generated_by: "template",
};
it("offers an approval request when an L1 cannot restrict", () => {
  const onRequest = vi.fn();
  render(<AgentBrief brief={brief} role="l1_analyst" onRun={vi.fn()} onRequest={onRequest} />);
  expect(screen.getByText("Recommended: Restrict account (L2)")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Request approval from L2" }));
  expect(onRequest).toHaveBeenCalledWith("restrict");
});
it("runs a permitted recommendation directly", () => {
  const onRun = vi.fn();
  render(
    <AgentBrief
      brief={{ ...brief, recommended_action: "place_lien", required_role: "l1_analyst" }}
      role="l1_analyst"
      onRun={onRun}
      onRequest={vi.fn()}
    />,
  );
  expect(screen.getByText("Recommended: Place lien (L1)")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Place lien" }));
  expect(onRun).toHaveBeenCalledWith("place_lien");
  expect(screen.getByText("FraudLens Agent")).toBeInTheDocument();
  expect(screen.getByText("High confidence")).toBeInTheDocument();
});
