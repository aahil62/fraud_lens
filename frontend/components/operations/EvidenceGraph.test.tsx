import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { Case } from "@/lib/operations";
import { EvidenceGraph } from "./EvidenceGraph";
it("attributes each beneficiary and instrument edge to the actual transaction owner", () => {
  const item = {
    case_id: "CASE-A", account_id: "A", channel: "upi", related_accounts: [],
    related_transactions: [
      { account_id: "A", beneficiary_id: "BEN-A", instrument_id: null },
      { account_id: "B", beneficiary_id: "BEN-B", instrument_id: null },
      { account_id: "B", beneficiary_id: null, instrument_id: "CARD-B" },
    ],
  } as unknown as Case;
  render(<EvidenceGraph cases={[item]} />);
  expect(screen.getByText("A → BEN-A")).toBeInTheDocument();
  expect(screen.getByText("B → BEN-B")).toBeInTheDocument();
  expect(screen.getByText("B → CARD-B")).toBeInTheDocument();
  expect(screen.queryByText("A → BEN-B")).not.toBeInTheDocument();
  expect(screen.queryByText("A → CARD-B")).not.toBeInTheDocument();
  expect(screen.getByText("account: B")).toBeInTheDocument();
});


it("separates beneficiary and instrument nodes and supports keyboard inspection", () => {
  const item = {case_id:"CASE-A",account_id:"A",channel:"upi",related_accounts:[],related_transactions:[{account_id:"A",beneficiary_id:"BEN-A",instrument_id:null},{account_id:"A",beneficiary_id:null,instrument_id:"CARD-A"}]} as unknown as Case;
  render(<EvidenceGraph cases={[item]}/>);
  const beneficiary=screen.getByRole("button",{name:"Inspect beneficiary BEN-A"});
  const instrument=screen.getByRole("button",{name:"Inspect instrument CARD-A"});
  expect(beneficiary.querySelector("circle")!.getAttribute("cy")).not.toBe(instrument.querySelector("circle")!.getAttribute("cy"));
  fireEvent.keyDown(beneficiary,{key:"Enter"});
  expect(screen.getByRole("status")).toHaveTextContent("BEN-A");
});
