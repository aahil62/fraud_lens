import { ArrowRight, LockSimple } from "@phosphor-icons/react";
import { rupees, type TraceHop, type Transaction } from "@/lib/operations";
const OUTCOME: Record<TraceHop["outcome"], [string, string]> = {
  held: ["Held", "good"],
  partially_recovered: ["Partially recovered", "warning"],
  funds_moved: ["Funds moved", "bad"],
  account_closed: ["Account closed", "ink"],
  pending: ["Awaiting bank", "muted"],
  released: ["Released", "muted"],
};
const masked = (id: string) => (id.length > 4 ? `…${id.slice(-4)}` : id);
export function FundTrail({
  victimAccountId,
  reportedMinor,
  trace,
  transactions = [],
  renderAction,
}: {
  victimAccountId: string;
  reportedMinor: number;
  trace: TraceHop[];
  /** Used only to label arrows with the inbound payment amounts. */
  transactions?: Pick<Transaction, "txn_id" | "amount_minor">[];
  /** Per-hop control (e.g. supervisor closure). Never offered for the victim node. */
  renderAction?: (hop: TraceHop) => React.ReactNode;
}) {
  const traced = trace.reduce((sum, hop) => sum + hop.traced_minor, 0);
  const held = trace.reduce((sum, hop) => sum + hop.lien_minor, 0);
  const amounts = new Map(transactions.map((t) => [t.txn_id, t.amount_minor]));
  const inbound = (hop: TraceHop) => {
    const known = hop.inbound_txn_ids.filter((id) => amounts.has(id));
    return known.length ? known.reduce((sum, id) => sum + (amounts.get(id) ?? 0), 0) : null;
  };
  return (
    <section className="ops-section fund-trail" aria-labelledby="fund-trail-heading">
      <div className="section-heading">
        <div>
          <h2 id="fund-trail-heading">Fund trail</h2>
          <p>
            Traced {rupees(traced)} across {trace.length} account(s) · held {rupees(held)}
          </p>
        </div>
      </div>
      <ol className="fund-chain">
        <li className="fund-node victim">
          <small>Victim</small>
          <strong className="identifier">{masked(victimAccountId)}</strong>
          <span>Reported {rupees(reportedMinor)}</span>
        </li>
        {trace.map((hop) => {
          const [label, tone] = OUTCOME[hop.outcome] ?? [hop.outcome, "muted"];
          return (
            <li className="fund-node" key={`${hop.hop}-${hop.account_id}`}>
              <span className="fund-arrow" aria-hidden="true">
                <ArrowRight size={16} />
              </span>
              <small>Hop {hop.hop}</small>
              <strong className="identifier">{masked(hop.account_id)}</strong>
              <dl>
                {inbound(hop) !== null && (
                  <div>
                    <dt>Received</dt>
                    <dd>{rupees(inbound(hop)!)}</dd>
                  </div>
                )}
                <div>
                  <dt>Traced</dt>
                  <dd>{rupees(hop.traced_minor)}</dd>
                </div>
                {(hop.moved_minor ?? 0) > 0 && (
                  <div>
                    <dt>Cashed out</dt>
                    <dd>{rupees(hop.moved_minor ?? 0)}</dd>
                  </div>
                )}
                <div>
                  <dt>On hold</dt>
                  <dd>
                    {hop.lien_minor > 0 && <LockSimple size={12} aria-hidden="true" />}
                    {rupees(hop.lien_minor)}
                  </dd>
                </div>
              </dl>
              <span className={`outcome-badge ${tone}`}>{label}</span>
              {hop.account_id !== victimAccountId && renderAction?.(hop)}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
