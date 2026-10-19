import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import LoginPage from "./page";
const mocks = vi.hoisted(() => ({ login: vi.fn(), push: vi.fn(), next: "/case?case_id=CASE-1" as string | null }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, refresh: vi.fn() }),
  useSearchParams: () => ({ get: () => mocks.next }),
}));
vi.mock("@/lib/auth", async (original) => ({ ...(await original<typeof import("@/lib/auth")>()), login: mocks.login }));
beforeEach(() => { mocks.login.mockReset().mockResolvedValue({}); mocks.push.mockReset(); });
afterEach(() => { vi.unstubAllEnvs(); });
const ROLES = ["Continue as L1 Analyst (K. Mehta)", "Continue as L2 Senior Analyst (R. Iyer)", "Continue as Fraud Supervisor (A. Sharma)"];
it("offers one-click demo roles in demo mode and routes to next", async () => {
  vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
  render(<LoginPage />);
  for (const name of ROLES) expect(await screen.findByRole("button", { name })).toBeInTheDocument();
  expect(screen.getByText("Open two windows with different roles to see the hand-off live.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: ROLES[0] }));
  await waitFor(() => expect(mocks.login).toHaveBeenCalledWith("kmehta", "fraudlens123"));
  await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/case?case_id=CASE-1"));
});
it("hides demo roles outside demo mode", async () => {
  vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");
  render(<LoginPage />);
  expect(await screen.findByRole("button", { name: "Open workspace" })).toBeInTheDocument();
  for (const name of ROLES) expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
});
it("hides the sign-up link on the public demo, where sign-up is disabled", async () => {
  vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");
  vi.stubEnv("NEXT_PUBLIC_PUBLIC_DEMO", "1");
  render(<LoginPage />);
  expect(await screen.findByRole("button", { name: ROLES[0] })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Create an account" })).not.toBeInTheDocument();
});
it("keeps the sign-up link for local use", async () => {
  vi.stubEnv("NEXT_PUBLIC_PUBLIC_DEMO", "");
  render(<LoginPage />);
  expect(await screen.findByRole("link", { name: "Create an account" })).toBeInTheDocument();
});
