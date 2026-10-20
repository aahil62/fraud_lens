"use client";
import Link from "next/link";
import { useState } from "react";
import { channelName, human } from "@/lib/operations";
import { EvidenceGraph } from "../EvidenceGraph";
import { useOperations } from "../OperationsProvider";
import { Loading, PageHeading } from "../Primitives";

export function NetworkView() {
  const { snapshot } = useOperations();
  const [selected, setSelected] = useState("");
  if (!snapshot) return <Loading />;
  const cases = selected ? snapshot.cases.filter((x) => x.case_id === selected) : snapshot.cases.slice(0, 8);
  return (
    <>
      <PageHeading
        title="Evidence connections"
        description="Inspect links from actual case evidence. A shared identifier does not itself prove fraud."
      />
      <section className="ops-section">
        <div className="filter-bar">
          <label>
            Investigation
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">Latest eight investigations</option>
              {snapshot.cases.map((item) => (
                <option key={item.case_id} value={item.case_id}>
                  {item.case_id}
                </option>
              ))}
            </select>
          </label>
          <p>Bounded evidence view · up to 16 nodes</p>
        </div>
        <div className="network-workspace">
          <EvidenceGraph cases={cases} />
          <div className="graph-case-list">
            {cases.map((item) => (
              <Link key={item.case_id} href={`/case?case_id=${encodeURIComponent(item.case_id)}`}>
                <strong>{item.account_id}</strong>
                <span>
                  {channelName(item.channel)} · {human(item.status)}
                </span>
                <small>{item.case_id} →</small>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
