import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import LensScene from "./LensScene";
const renderer = vi.hoisted(() => vi.fn());
vi.mock("three", () => ({ WebGLRenderer: renderer }));
afterEach(() => {
  vi.unstubAllGlobals();
  renderer.mockClear();
});
it("keeps a complete static optic without initializing WebGL under reduced motion", () => {
  const add = vi.fn(),
    remove = vi.fn();
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      addEventListener: add,
      removeEventListener: remove,
    })),
  );
  const { container, unmount } = render(<LensScene channel="card" />);
  expect(screen.getByRole("img", { name: /optical lens/ })).toBeInTheDocument();
  expect(container.querySelector(".lens-poster")).toBeInTheDocument();
  expect(container.querySelector("canvas")).not.toBeInTheDocument();
  expect(renderer).not.toHaveBeenCalled();
  unmount();
  expect(remove).toHaveBeenCalled();
});
it("keeps the static optic when the browser only has software WebGL", async () => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
  const gl = {
    getExtension: () => ({ UNMASKED_RENDERER_WEBGL: 1 }),
    getParameter: () => "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device))",
  };
  const getContext = vi
    .spyOn(HTMLCanvasElement.prototype, "getContext")
    .mockReturnValue(gl as unknown as RenderingContext);
  const { container } = render(<LensScene channel="upi" />);
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(container.querySelector(".lens-poster")).toBeInTheDocument();
  expect(renderer).not.toHaveBeenCalled();
  getContext.mockRestore();
});
it("does not initialize motion APIs or WebGL when the visitor pauses 3D", () => {
  const media = vi.fn();
  vi.stubGlobal("matchMedia", media);
  const { container } = render(<LensScene channel="upi" animated={false} />);
  expect(container.querySelector(".lens-poster")).toBeInTheDocument();
  expect(media).not.toHaveBeenCalled();
  expect(renderer).not.toHaveBeenCalled();
});
