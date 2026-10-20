import { CheckCircle, ShieldCheck } from "@phosphor-icons/react";
import { type Case, human } from "@/lib/operations";

/** Detection reasons and each signal's contribution. */
export function FlaggedReasons({ item }: { item: Case }) {
  return (
    <section className="ops-section">
      <div className="section-heading">
        <div><h2>Why this payment was flagged</h2><p>Detection reasons and individual signal contributions.</p></div>
      </div>
      <ul className="reason-list">
        {item.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
      </ul>
      <div className="signal-list">
        {item.signals.map((signal, i) => (
          <div key={`${signal.name}-${i}`}>
            <div><strong>{human(signal.name)}</strong><span className="numeric">{(signal.score * 100).toFixed(1)}</span></div>
            <meter min="0" max="100" value={signal.score * 100} aria-label={`${signal.name} score`} />
            {signal.reasons.length > 0 && <p>{signal.reasons.join(" · ")}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

function outcomeTitle(item: Case) {
  if (item.verdict === "false_positive") {
    return item.status === "resolved" ? "False positive resolved" : "Awaiting release acknowledgement";
  }
  if (item.verdict === "fraud") return "Fraud confirmed by analyst";
  return "Review the detected pattern";
}

/** What the current verdict means for the analyst. */
export function VerdictNote({ item }: { item: Case }) {
  const Icon = item.status === "resolved" ? CheckCircle : ShieldCheck;
  const text = item.verdict === "unreviewed"
    ? "Automated detection is a signal. Investigate the triggering evidence and account history before recording a verdict."
    : item.notes || "Check delivery status and the case timeline for the latest outcome.";
  return (
    <section className="recommendation">
      <strong><Icon size={18} weight="duotone" />{outcomeTitle(item)}</strong>
      <p>{text}</p>
    </section>
  );
}
