"use client";
import Link from "next/link";
import { useState } from "react";
import { type Case, channelName, human } from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { Empty, Loading, PageHeading } from "./Primitives";
export function EvidenceGraph({ cases }: { cases: Case[] }) {
  const [selectedNode, setSelectedNode] = useState("");
  const nodes = new Map<string, { id: string; kind: string }>();
  const edges: { from: string; to: string; label: string }[] = [];
  cases.slice(0, 8).forEach((item) => {
    nodes.set(item.account_id, { id: item.account_id, kind: "account" });
    nodes.set(item.case_id, { id: item.case_id, kind: "case" });
    edges.push({
      from: item.account_id,
      to: item.case_id,
      label: channelName(item.channel),
    });
    item.related_accounts.slice(0, 4).forEach((account) => {
      nodes.set(account, { id: account, kind: "account" });
      edges.push({ from: item.account_id, to: account, label: "shared-device evidence" });
    });
    item.related_transactions.slice(0, 8).forEach((txn) => {
      nodes.set(txn.account_id, { id: txn.account_id, kind: "account" });
      const target = txn.beneficiary_id || txn.instrument_id;
      if (target) {
        nodes.set(target, {
          id: target,
          kind: txn.beneficiary_id ? "beneficiary" : "instrument",
        });
        if (!edges.some((x) => x.from === txn.account_id && x.to === target))
          edges.push({
            from: txn.account_id,
            to: target,
            label: txn.beneficiary_id ? "beneficiary" : "instrument",
          });
      }
    });
  });
  const list = [...nodes.values()].slice(0, 16);
  const group = (kind: string) => kind === "case" || kind === "account" ? kind : "reference";
  const maxRows = Math.max(1, ...["case", "account", "reference"].map(kind => list.filter(node=>group(node.kind)===kind).length));
  const graphHeight = Math.max(380, 110 + maxRows * 65);
  const positions = new Map(list.map((node, i) => {
    const peers = list.filter(x => group(x.kind) === group(node.kind));
    const index = peers.findIndex(x => x.id === node.id);
    const column = node.kind === "case" ? 92 : node.kind === "account" ? 253 : 428;
    return [node.id, { x: column + (i % 2 ? 8 : -8), y: 55 + (index + .5) * ((graphHeight - 110) / peers.length) }];
  }));
  const selected = list.find(x => x.id === selectedNode);
  const linked = new Set(edges.filter(x => x.from === selectedNode || x.to === selectedNode).flatMap(x=>[x.from,x.to]));
  if (!list.length) return <Empty>No evidence connections yet.</Empty>;
  return (
    <figure className="evidence-graph">
      <svg
        viewBox={`0 0 520 ${graphHeight}`}
        role="group"
        aria-label="Evidence graph connecting accounts, investigations, beneficiaries and payment instruments"
      >
        <text x="85" y="28" textAnchor="middle" fill="#626d80" fontSize="9">INVESTIGATIONS</text>
        <text x="253" y="28" textAnchor="middle" fill="#626d80" fontSize="9">ACCOUNTS</text>
        <text x="425" y="28" textAnchor="middle" fill="#626d80" fontSize="9">CONNECTED REFERENCES</text>
        <g>
          {edges.map((edge, i) => {
            const a = positions.get(edge.from),
              b = positions.get(edge.to);
            return a && b ? (
              <path
                key={i}
                d={`M${a.x},${a.y} C${(a.x+b.x)/2},${a.y} ${(a.x+b.x)/2},${b.y} ${b.x},${b.y}`}
                fill="none"
                stroke={selected && (edge.from === selectedNode || edge.to === selectedNode) ? "#7187dc" : "#d9e0f1"}
                strokeWidth="1.4"
                opacity={selected && edge.from !== selectedNode && edge.to !== selectedNode ? .3 : 1}
              >
                <title>
                  {edge.from} → {edge.to}: {edge.label}
                </title>
              </path>
            ) : null;
          })}
        </g>
        {list.map((node) => {
          const p = positions.get(node.id)!;
          return (
            <g key={node.id} role="button" tabIndex={0} aria-label={`Inspect ${node.kind} ${node.id}`} onClick={()=>setSelectedNode(selectedNode===node.id?"":node.id)} onKeyDown={event=>{if(event.key==="Enter" || event.key===" "){event.preventDefault();setSelectedNode(selectedNode===node.id?"":node.id);}}} style={{cursor:"pointer",opacity:selected && !linked.has(node.id) && node.id!==selectedNode? .35:1}}>
              <circle cx={p.x} cy={p.y} r={node.kind==="account"?22:16} fill="white" stroke={selectedNode===node.id?"#637bd5":"#e0e6f3"} strokeWidth="1.4"/>
              <circle
                cx={p.x}
                cy={p.y}
                r={node.kind === "account" ? 13 : 8}
                fill={
                  node.kind === "case"
                    ? "#d8a051"
                    : node.kind === "account"
                      ? "#677fce"
                      : "#92a2be"
                }
              />
              <text
                x={p.x}
                y={p.y + 35}
                textAnchor="middle"
                fill="#596b8c"
                fontSize="9"
              >
                {node.id.length > 16 ? node.id.slice(0, 12) + "…" : node.id}
              </text>
              <title>
                {node.kind}: {node.id}
              </title>
            </g>
          );
        })}
      </svg>
      {selected && <div className="graph-node-detail" role="status"><strong>{human(selected.kind)}</strong><span>{selected.id}</span><small>{edges.filter(x=>x.from===selected.id||x.to===selected.id).length} evidence links</small></div>}
      <figcaption>
        ● Account <span>● Investigation</span> ● Beneficiary / instrument
        {nodes.size > 16 ? " · Showing 16 nodes" : ""}
      </figcaption>
      <details className="graph-evidence-list">
        <summary>Inspect evidence links</summary>
        <ul>{edges.filter(edge => positions.has(edge.from) && positions.has(edge.to)).map((edge, index) => <li key={index}><strong>{edge.label}</strong><span>{edge.from} → {edge.to}</span></li>)}</ul>
      </details>
    </figure>
  );
}
export function NetworkView() {
  const { snapshot } = useOperations();
  const [selected, setSelected] = useState("");
  if (!snapshot) return <Loading />;
  const cases = selected
    ? snapshot.cases.filter((x) => x.case_id === selected)
    : snapshot.cases.slice(0, 8);
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
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
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
              <Link
                key={item.case_id}
                href={`/case?case_id=${encodeURIComponent(item.case_id)}`}
              >
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
