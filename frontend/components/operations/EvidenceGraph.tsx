"use client";
import { useState } from "react";
import { type Case, human } from "@/lib/operations";
import { buildEvidenceGraph, nodeGroup } from "./evidenceGraphLayout";
import { Empty } from "./Primitives";
export function EvidenceGraph({ cases }: { cases: Case[] }) {
  const [selectedNode, setSelectedNode] = useState("");
  const { list, edges, positions, graphHeight, nodeCount } = buildEvidenceGraph(cases);
  const selected = list.find((x) => x.id === selectedNode);
  const linked = new Set(
    edges.filter((x) => x.from === selectedNode || x.to === selectedNode).flatMap((x) => [x.from, x.to]),
  );
  if (!list.length) return <Empty>No evidence connections yet.</Empty>;
  return (
    <figure className="evidence-graph">
      <svg
        viewBox={`0 0 520 ${graphHeight}`}
        role="group"
        aria-label="Evidence graph connecting accounts, investigations, beneficiaries and payment instruments"
      >
        <text x="85" y="28" textAnchor="middle" className="graph-heading" fontSize="9">
          INVESTIGATIONS
        </text>
        <text x="253" y="28" textAnchor="middle" className="graph-heading" fontSize="9">
          ACCOUNTS
        </text>
        <text x="425" y="28" textAnchor="middle" className="graph-heading" fontSize="9">
          CONNECTED REFERENCES
        </text>
        <g>
          {edges.map((edge, i) => {
            const a = positions.get(edge.from),
              b = positions.get(edge.to);
            return a && b ? (
              <path
                key={i}
                d={`M${a.x},${a.y} C${(a.x + b.x) / 2},${a.y} ${(a.x + b.x) / 2},${b.y} ${b.x},${b.y}`}
                fill="none"
                className={
                  selected && (edge.from === selectedNode || edge.to === selectedNode)
                    ? "graph-edge is-active"
                    : "graph-edge"
                }
                strokeWidth="1.4"
                opacity={selected && edge.from !== selectedNode && edge.to !== selectedNode ? 0.3 : 1}
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
            <g
              key={node.id}
              role="button"
              tabIndex={0}
              aria-label={`Inspect ${node.kind} ${node.id}`}
              onClick={() => setSelectedNode(selectedNode === node.id ? "" : node.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedNode(selectedNode === node.id ? "" : node.id);
                }
              }}
              style={{
                cursor: "pointer",
                opacity: selected && !linked.has(node.id) && node.id !== selectedNode ? 0.35 : 1,
              }}
            >
              <circle
                cx={p.x}
                cy={p.y}
                r={node.kind === "account" ? 22 : 16}
                className={selectedNode === node.id ? "graph-node-ring is-selected" : "graph-node-ring"}
                strokeWidth="1.4"
              />
              <circle
                cx={p.x}
                cy={p.y}
                r={node.kind === "account" ? 13 : 8}
                className={`graph-node-dot graph-node-${nodeGroup(node.kind)}`}
              />
              <text x={p.x} y={p.y + 35} textAnchor="middle" className="graph-label" fontSize="9">
                {node.id.length > 16 ? node.id.slice(0, 12) + "…" : node.id}
              </text>
              <title>
                {node.kind}: {node.id}
              </title>
            </g>
          );
        })}
      </svg>
      {selected && (
        <div className="graph-node-detail" role="status">
          <strong>{human(selected.kind)}</strong>
          <span>{selected.id}</span>
          <small>
            {edges.filter((x) => x.from === selected.id || x.to === selected.id).length} evidence links
          </small>
        </div>
      )}
      <figcaption>
        ● Account <span>● Investigation</span> ● Beneficiary / instrument
        {nodeCount > list.length ? " · Showing 16 nodes" : ""}
      </figcaption>
      <details className="graph-evidence-list">
        <summary>Inspect evidence links</summary>
        <ul>
          {edges
            .filter((edge) => positions.has(edge.from) && positions.has(edge.to))
            .map((edge, index) => (
              <li key={index}>
                <strong>{edge.label}</strong>
                <span>
                  {edge.from} → {edge.to}
                </span>
              </li>
            ))}
        </ul>
      </details>
    </figure>
  );
}
