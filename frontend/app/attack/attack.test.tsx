import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AttackError } from "@/lib/attacks";
import AttackPage from "./page";
const mocks = vi.hoisted(() => ({ launch: vi.fn(), status: vi.fn(), report: vi.fn() }));
vi.mock("@/lib/attacks", async (original) => ({
  ...(await original<typeof import("@/lib/attacks")>()),
  launchAttack: mocks.launch, getAttack: mocks.status, reportTo1930: mocks.report,
}));
const LABELS = ["Scam payment sent", "FraudLens flagged it", "Bank protection requested", "Bank confirmed protection", "Analyst picked it up", "Verdict recorded"];
beforeEach(() => {
  mocks.launch.mockReset(); mocks.status.mockReset(); mocks.report.mockReset();
});
it("lists the four scams and shows the amount slider only for mule layering", () => {
  render(<AttackPage />);
  for (const name of ["Mule layering", "SIM-swap takeover", "Card testing", "ATM cash-out"])
    expect(screen.getByRole("radio", { name: new RegExp(name) })).toBeInTheDocument();
  expect(screen.getByRole("slider", { name: /Scam amount/ })).toHaveValue("48000");
  fireEvent.click(screen.getByRole("radio", { name: /Card testing/ }));
  expect(screen.queryByRole("slider")).not.toBeInTheDocument();
});
it("renders the six-step live timeline after a launch", async () => {
  mocks.launch.mockResolvedValue({ attack_id: "ATK-000000000001", status_url: "/public/attacks/ATK-000000000001" });
  mocks.status.mockResolvedValue({ attack_id: "ATK-000000000001", typology: "card_testing", outcome: "in_progress", case_id_masked: "…ABCD",
    complaint_id: null, traced_total_minor: 0, held_total_minor: 0,
    steps: LABELS.map((label, i) => ({ label, status: i < 2 ? "done" : "pending", at: null })) });
  render(<AttackPage />);
  fireEvent.click(screen.getByRole("radio", { name: /Card testing/ }));
  fireEvent.click(screen.getByRole("button", { name: "Launch attack" }));
  await waitFor(() => expect(mocks.launch).toHaveBeenCalledWith("card_testing", 4800000));
  for (const label of LABELS) expect(await screen.findByText(label)).toBeInTheDocument();
  expect(screen.getAllByRole("listitem").filter((li) => li.dataset.status === "done")).toHaveLength(2);
});
it("shows the API's friendly rate-limit message", async () => {
  mocks.launch.mockRejectedValue(new AttackError(429, "Too many simulated attacks. Try again in a few minutes."));
  render(<AttackPage />);
  fireEvent.click(screen.getByRole("button", { name: "Launch attack" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Too many simulated attacks. Try again in a few minutes.");
});
