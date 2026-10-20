import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { getToken, logout, safeNextPath, setSession } from "./auth";

// Node's native localStorage shadows jsdom in this runtime; isolate browser storage.
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
    removeItem: (key: string) => {
      values.delete(key);
    },
    clear: () => values.clear(),
  });
});
afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
for (const available of [true, false]) {
  it(`clears the local session after attempting audited logout (API available: ${available})`, async () => {
    setSession("session-token", { username: "kmehta", display_name: "K. Mehta", role: "l1_analyst" });
    const request = vi.spyOn(globalThis, "fetch");
    if (available) request.mockResolvedValue(new Response('{"ok":true}'));
    else request.mockRejectedValue(new TypeError("offline"));
    await logout();
    expect(request).toHaveBeenCalledWith(
      expect.stringContaining("/auth/logout"),
      expect.objectContaining({
        method: "POST",
        headers: { Authorization: "Bearer session-token" },
      }),
    );
    expect(getToken()).toBeNull();
    expect(localStorage.getItem("fraudlens_analyst")).toBeNull();
    expect(document.cookie).not.toContain("fraudlens_token=");
  });
}

it("only follows a same-origin next path after sign-in", () => {
  const origin = "http://localhost:3000";
  expect(safeNextPath("/case?case_id=CASE-1", origin)).toBe("/case?case_id=CASE-1");
  expect(safeNextPath(null, origin)).toBe("/dashboard");
  for (const unsafe of [
    "//evil.com",
    "/\\evil.com",
    "/\t/evil.com",
    "/\n/evil.com",
    "https://evil.com",
    "evil",
  ]) {
    expect(safeNextPath(unsafe, origin)).toBe("/dashboard");
  }
});

it("marks the session cookie Secure only over HTTPS", () => {
  const writes: string[] = [];
  const cookie = vi.spyOn(document, "cookie", "set").mockImplementation((value) => {
    writes.push(value);
  });
  const analyst = { username: "kmehta", display_name: "K. Mehta", role: "l1_analyst" } as const;
  setSession("token", analyst);
  vi.stubGlobal("location", { protocol: "https:" });
  setSession("token", analyst);
  expect(writes[0]).not.toContain("secure");
  expect(writes[1]).toContain("; secure");
  cookie.mockRestore();
});
