"use client";
import { useState } from "react";
import { Copy, Robot } from "@phosphor-icons/react";
import { ACTION_LABEL, ROLE_SHORT, can, type Brief, type CaseAction, type Role } from "@/lib/operations";
import { RoleChip } from "./RoleChip";
export function AgentBrief({ brief, role, busy = false, onRun, onRequest }: {
  brief: Brief;
  role: Role | undefined;
  busy?: boolean;
  onRun: (action: CaseAction) => void;
  onRequest: (action: CaseAction) => void;
}) {
  const [copied, setCopied] = useState(false);
  const action = brief.recommended_action;
  const allowed = can(role, action);
  async function copy() {
    try {
      await navigator.clipboard.writeText(brief.ncrp_narrative);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  return <section className="ops-section agent-brief" aria-labelledby="agent-brief-heading">
    <div className="section-heading">
      <div><span className="agent-label"><Robot size={15} weight="duotone" aria-hidden="true" />FraudLens Agent</span>
        <h2 id="agent-brief-heading">{brief.typology}</h2></div>
      <span className={`confidence-chip ${brief.confidence}`}>{brief.confidence[0].toUpperCase() + brief.confidence.slice(1)} confidence</span>
    </div>
    <p className="agent-summary">{brief.summary}</p>
    {brief.evidence.length > 0 && <ul className="reason-list">{brief.evidence.map((item, i) => <li key={i}>{item}</li>)}</ul>}
    <div className="agent-recommendation">
      <span><strong>Recommended: {ACTION_LABEL[action]} ({ROLE_SHORT[brief.required_role]})</strong>
        <RoleChip role={brief.required_role} /></span>
      {allowed
        ? <button className="primary-button" disabled={busy} onClick={() => onRun(action)}>{ACTION_LABEL[action]}</button>
        : <button disabled={busy} onClick={() => onRequest(action)}>Request approval from {ROLE_SHORT[brief.required_role]}</button>}
    </div>
    {brief.next_steps.length > 0 && <fieldset className="agent-steps"><legend>Next steps</legend>
      {brief.next_steps.map((step, i) => <label key={i}><input type="checkbox" />{step}</label>)}</fieldset>}
    <details className="agent-narrative"><summary>Draft NCRP narrative</summary>
      <p>{brief.ncrp_narrative}</p>
      <button onClick={() => { void copy(); }}><Copy size={14} aria-hidden="true" />{copied ? "Copied" : "Copy"}</button>
      <p className="fine-print">A draft for analyst review. FraudLens does not file anything externally.</p>
    </details>
    <p className="fine-print">Drafted {brief.generated_by === "llm" ? "with optional local wording" : "from case facts"}. The agent recommends; analysts decide.</p>
  </section>;
}
