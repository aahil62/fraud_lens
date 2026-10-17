import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { type Case, OperationsError } from "@/lib/operations";
import { DecisionPanel } from "./CaseWorkspace";
const mocks = vi.hoisted(() => ({
  decide: vi.fn(),
  refresh: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("./OperationsProvider", () => ({
  useOperations: () => ({ refresh: mocks.refresh }),
}));
vi.mock("@/lib/operations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/operations")>()),
  decideCase: mocks.decide,
}));
const item = { case_id: "case-7", version: 7, status: "new" } as Case;
beforeEach(() => {
  mocks.decide.mockReset();
  mocks.refresh.mockClear();
});
it("keeps verdict controls disabled until evidence notes are entered", () => {
  render(<DecisionPanel item={item} onUpdated={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Confirm fraud" })).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Transfer followed a new device login" },
  });
  expect(
    screen.getByRole("button", { name: "Confirm fraud" }),
  ).not.toBeDisabled();
});
it("sends the rendered version and refreshes after a successful false-positive decision", async () => {
  const updated = { ...item, version: 8 };
  mocks.decide.mockResolvedValue(updated);
  const onUpdated = vi.fn();
  render(<DecisionPanel item={item} onUpdated={onUpdated} />);
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Customer verified legitimate activity" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Mark false positive & release" }),
  );
  await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(updated));
  expect(mocks.decide).toHaveBeenCalledWith(
    "case-7",
    "false_positive",
    7,
    "Customer verified legitimate activity",
  );
  expect(mocks.refresh).toHaveBeenCalled();
});
it("shows a version conflict and does not silently resubmit an analyst verdict", async () => {
  mocks.decide.mockRejectedValue(new OperationsError(409, "stale"));
  render(<DecisionPanel item={item} onUpdated={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Start investigation" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Another update changed this case",
  );
  expect(mocks.decide).toHaveBeenCalledTimes(1);
  expect(mocks.refresh).toHaveBeenCalled();
});
it("displays a service failure while preserving investigation notes", async () => {
  mocks.decide.mockRejectedValue(new Error("Bank delivery unavailable"));
  render(<DecisionPanel item={item} onUpdated={vi.fn()} />);
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Evidence retained" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Confirm fraud" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("textbox")).toHaveValue("Evidence retained");
});
it.each(["investigating", "resolved"])("locks all decisions after a false-positive verdict while %s", (status) => {
  render(<DecisionPanel item={{...item, status, verdict: "false_positive"}} onUpdated={vi.fn()} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Attempt to contradict release" } });
  for (const button of screen.getAllByRole("button")) expect(button).toBeDisabled();
  expect(screen.getByText(status === "resolved" ? /False-positive verdict is final/ : /Release is awaiting bank confirmation/)).toBeInTheDocument();
});
it("allows reversing a resolved fraud verdict while preventing other resolved-case decisions", async () => {
  mocks.decide.mockResolvedValue({...item, version:8, verdict:"false_positive"});
  render(<DecisionPanel item={{...item, status:"resolved", verdict:"fraud"}} onUpdated={vi.fn()} />);
  fireEvent.change(screen.getByRole("textbox"), {target:{value:"Verified account holder; fraud decision overturned"}});
  expect(screen.getByRole("button",{name:"Start investigation"})).toBeDisabled();
  expect(screen.getByRole("button",{name:"Escalate"})).toBeDisabled();
  expect(screen.getByRole("button",{name:"Confirm fraud"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button",{name:"Mark false positive & release"}));
  await waitFor(()=>expect(mocks.decide).toHaveBeenCalledWith("case-7","false_positive",7,"Verified account holder; fraud decision overturned"));
});
