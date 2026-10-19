import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { RoleChip } from "./RoleChip";
it.each([
  ["l1_analyst", "L1", "L1 Analyst"],
  ["l2_analyst", "L2", "L2 Senior Analyst"],
  ["supervisor", "Supervisor", "Fraud Supervisor"],
] as const)("renders the short label for %s", (role, short, full) => {
  render(<RoleChip role={role} />);
  const chip = screen.getByText(short);
  expect(chip).toHaveAttribute("title", full);
  expect(chip.className).toContain(`role-chip-${role}`);
});
