import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ApprovalPanel } from "./ApprovalPanel";
const approval = { approval_id: "APR-1", action: "confirm_fraud" as const, requested_by: "kmehta", required_role: "l2_analyst" as const,
  notes: "Pass-through within minutes", requested_at: "2026-10-19T01:00:00Z" };
it("keeps reject disabled until notes are entered", () => {
  const onDecide = vi.fn();
  render(<ApprovalPanel mode="decide" approval={approval} requesterName="K. Mehta" onDecide={onDecide} />);
  expect(screen.getByText("K. Mehta requests: Confirm fraud — Pass-through within minutes")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Customer confirmed the payee" } });
  fireEvent.click(screen.getByRole("button", { name: "Reject" }));
  expect(onDecide).toHaveBeenCalledWith(false, "Customer confirmed the payee");
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(onDecide).toHaveBeenCalledWith(true, "Customer confirmed the payee");
});
it("requires notes before sending an approval request", () => {
  const onSubmit = vi.fn();
  render(<ApprovalPanel mode="request" action="confirm_fraud" requiredRole="l2_analyst" onSubmit={onSubmit} onCancel={vi.fn()} />);
  const send = screen.getByRole("button", { name: "Send request to L2" });
  expect(send).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Funds left within four minutes" } });
  fireEvent.click(send);
  expect(onSubmit).toHaveBeenCalledWith("Funds left within four minutes");
});
