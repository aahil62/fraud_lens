import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { decideCase, newestSnapshot, OperationsError, opsFetch, type Snapshot } from "../operations";
const session = vi.hoisted(() => ({ token: "test-session" as string | null }));
vi.mock("../auth", () => ({ getToken: () => session.token }));
describe("authenticated operations contract", () => {
  beforeEach(() => {
    session.token = "test-session";
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });
  it("uses the case version and authenticated actor session for a verdict", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ version: 4 }) });
    vi.stubGlobal("fetch", fetcher);
    await decideCase("case/a", "confirm_fraud", 3, " Observed linked transfers ");
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining("/ops/cases/case%2Fa/decision"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-session",
        }),
        body: JSON.stringify({
          action: "confirm_fraud",
          expected_version: 3,
          notes: "Observed linked transfers",
        }),
      }),
    );
  });
  it.each(["confirm_fraud", "false_positive"] as const)("requires evidence notes for %s", (action) => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(() => decideCase("case1", action, 1, "  ")).toThrow("Add investigation notes");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("preserves HTTP409 so the interface can require a fresh review", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: "Stale version" }),
      }),
    );
    await expect(decideCase("case1", "investigate", 1, "reviewing")).rejects.toMatchObject({
      status: 409,
      message: "Stale version",
    });
  });
  it("rejects unauthenticated operations without issuing a request", async () => {
    session.token = null;
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(opsFetch("/snapshot")).rejects.toBeInstanceOf(OperationsError);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("retains a meaningful server rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "Bank unavailable" }),
      }),
    );
    await expect(opsFetch("/process")).rejects.toMatchObject({
      status: 503,
      message: "Bank unavailable",
    });
  });
});
describe("shared snapshot ordering", () => {
  const snapshot = (cursor: number, transactions: number) =>
    ({ cursor, counts: { transactions } }) as Snapshot;
  it("does not roll counts backward when an older request finishes late", () => {
    const current = snapshot(12, 150);
    expect(newestSnapshot(current, snapshot(11, 140))).toBe(current);
  });
  it("accepts a newer authoritative snapshot as one object", () => {
    const next = snapshot(13, 160);
    expect(newestSnapshot(snapshot(12, 150), next)).toBe(next);
  });
  it("accepts an initial and equal-cursor refresh", () => {
    const first = snapshot(0, 0);
    expect(newestSnapshot(null, first)).toBe(first);
    const bankRefresh = snapshot(0, 1);
    expect(newestSnapshot(first, bankRefresh)).toBe(bankRefresh);
  });
});
