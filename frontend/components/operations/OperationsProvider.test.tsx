import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { type Snapshot } from "@/lib/operations";
import { OperationsProvider, useOperations } from "./OperationsProvider";
vi.mock("@/lib/auth", () => ({ getToken: () => "test-session" }));
function Consumer() {
  const { snapshot, connected, error, refresh } = useOperations();
  return <div><span data-testid="counts">{snapshot ? `${snapshot.counts.transactions}/${snapshot.counts.resolved}` : "loading"}</span><span data-testid="connection">{connected ? "connected" : "disconnected"}</span><span role="status">{error}</span><button onClick={() => { void refresh().catch(() => {}); }}>Recover</button></div>;
}
afterEach(() => { vi.unstubAllGlobals(); });
it("retains the last consistent counts on a failed snapshot and recovers from the same authenticated source", async () => {
  const response = (cursor: number, transactions: number, resolved: number) => ({ ok: true, json: async () => ({ cursor, counts: { transactions, resolved } } as Snapshot) });
  const snapshots = [response(1, 12, 2), { ok: false, status: 503, json: async () => ({ detail: "Operations unavailable" }) }, response(3, 19, 4)];
  const fetcher = vi.fn().mockImplementation(async (url: string) => {
    if (url.includes("/events")) throw new Error("Stream interrupted");
    return snapshots.shift();
  });
  vi.stubGlobal("fetch", fetcher);
  render(<OperationsProvider><Consumer /></OperationsProvider>);
  await waitFor(() => expect(screen.getByTestId("counts")).toHaveTextContent("12/2"));
  fireEvent.click(screen.getByRole("button", { name: "Recover" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Operations unavailable"));
  expect(screen.getByTestId("counts")).toHaveTextContent("12/2");
  fireEvent.click(screen.getByRole("button", { name: "Recover" }));
  await waitFor(() => expect(screen.getByTestId("counts")).toHaveTextContent("19/4"));
  expect(fetcher.mock.calls.every(([, options]) => options.headers.Authorization === "Bearer test-session")).toBe(true);
  expect(screen.getByTestId("connection")).toHaveTextContent("disconnected");
});
