import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { type Snapshot } from "@/lib/operations";
import { OperationsProvider, useOperations } from "./OperationsProvider";
vi.mock("@/lib/auth", () => ({ getToken: () => "test-session" }));
function Consumer() {
  const { snapshot, connected, error, refresh } = useOperations();
  return (
    <div>
      <span data-testid="counts">
        {snapshot ? `${snapshot.counts.transactions}/${snapshot.counts.resolved}` : "loading"}
      </span>
      <span data-testid="connection">{connected ? "connected" : "disconnected"}</span>
      <span role="status">{error}</span>
      <button
        onClick={() => {
          void refresh().catch(() => {});
        }}
      >
        Recover
      </button>
    </div>
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
});
it("retains the last consistent counts on a failed snapshot and recovers from the same authenticated source", async () => {
  const response = (cursor: number, transactions: number, resolved: number) => ({
    ok: true,
    json: async () => ({ cursor, counts: { transactions, resolved } }) as Snapshot,
  });
  const snapshots = [
    response(1, 12, 2),
    { ok: false, status: 503, json: async () => ({ detail: "Operations unavailable" }) },
    response(3, 19, 4),
  ];
  const fetcher = vi.fn().mockImplementation(async (url: string) => {
    if (url.includes("/events")) throw new Error("Stream interrupted");
    if (url.includes("/presence/heartbeat")) return { ok: true, json: async () => ({ ok: true }) };
    return snapshots.shift();
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <OperationsProvider>
      <Consumer />
    </OperationsProvider>,
  );
  await waitFor(() => expect(screen.getByTestId("counts")).toHaveTextContent("12/2"));
  fireEvent.click(screen.getByRole("button", { name: "Recover" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Operations unavailable"));
  expect(screen.getByTestId("counts")).toHaveTextContent("12/2");
  fireEvent.click(screen.getByRole("button", { name: "Recover" }));
  await waitFor(() => expect(screen.getByTestId("counts")).toHaveTextContent("19/4"));
  expect(
    fetcher.mock.calls.every(([, options]) => options.headers.Authorization === "Bearer test-session"),
  ).toBe(true);
  expect(screen.getByTestId("connection")).toHaveTextContent("disconnected");
});
function CaseOpener() {
  const { setCurrentCase } = useOperations();
  return <button onClick={() => setCurrentCase("CASE-42")}>Open case</button>;
}
it("sends a presence heartbeat on mount and immediately when a case opens", async () => {
  const fetcher = vi.fn().mockImplementation(async (url: string) => {
    if (url.includes("/events")) throw new Error("Stream interrupted");
    if (url.includes("/presence/heartbeat")) return { ok: true, json: async () => ({ ok: true }) };
    return { ok: true, json: async () => ({ cursor: 1, counts: {} }) };
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <OperationsProvider>
      <CaseOpener />
    </OperationsProvider>,
  );
  const beats = () =>
    fetcher.mock.calls
      .filter(([url]) => url.includes("/presence/heartbeat"))
      .map(([, options]) => JSON.parse(options.body));
  await waitFor(() => expect(beats()).toContainEqual({ current_case_id: null }));
  fireEvent.click(screen.getByRole("button", { name: "Open case" }));
  await waitFor(() => expect(beats()).toContainEqual({ current_case_id: "CASE-42" }));
});
it("fetches again when an update arrives while a snapshot request is in flight", async () => {
  let release: (value: unknown) => void = () => {};
  const first = new Promise((resolve) => {
    release = resolve;
  });
  const snapshots = [
    first,
    Promise.resolve({
      ok: true,
      json: async () => ({ cursor: 2, counts: { transactions: 2, resolved: 1 } }),
    }),
  ];
  const fetcher = vi.fn().mockImplementation(async (url: string) => {
    if (url.includes("/events")) throw new Error("Stream interrupted");
    if (url.includes("/presence/heartbeat")) return { ok: true, json: async () => ({ ok: true }) };
    return snapshots.shift();
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <OperationsProvider>
      <Consumer />
    </OperationsProvider>,
  );
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("/snapshot"))).toBe(true));
  fireEvent.click(screen.getByRole("button", { name: "Recover" }));
  release({ ok: true, json: async () => ({ cursor: 1, counts: { transactions: 1, resolved: 0 } }) });
  await waitFor(() => expect(screen.getByTestId("counts")).toHaveTextContent("2/1"));
});
