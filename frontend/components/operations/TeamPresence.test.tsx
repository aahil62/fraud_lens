import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { TeamMember } from "@/lib/operations";
import { TeamPresence } from "./TeamPresence";
const member = (i: number, online = true): TeamMember => ({
  username: `user${i}`, display_name: `A${i}. Analyst`, role: "l1_analyst", role_label: "L1 Analyst", online,
  last_seen: null, current_case_id: i === 0 ? "CASE-1234" : null, open_assigned: 0, resolved_today: 0,
});
it("shows only online analysts", () => {
  render(<TeamPresence team={[member(0), member(1, false)]} />);
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  expect(screen.getByTitle("A0. Analyst · L1 Analyst · on CASE-1234")).toBeInTheDocument();
});
it("caps avatars at five with an overflow count", () => {
  render(<TeamPresence team={Array.from({ length: 7 }, (_, i) => member(i))} />);
  expect(screen.getAllByRole("listitem")).toHaveLength(6);
  expect(screen.getByText("+2")).toBeInTheDocument();
});
