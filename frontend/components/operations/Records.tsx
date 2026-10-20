"use client";
import { type AuditEvent, type Case, type Transaction, dateTime, human, money } from "@/lib/operations";
import { CaseLink, ChannelLabel, Empty, Status } from "./Primitives";
import { initials } from "./useAnalyst";

function Owner({ item }: { item: Case }) {
  if (!item.assignee) return <span className="muted">Unassigned</span>;
  const name = item.assigned_to ?? item.assignee;
  return (
    <span className="owner-cell">
      <span className="presence-avatar small" aria-hidden="true">
        {initials(name)}
      </span>
      {name}
    </span>
  );
}
export function CaseTable({
  cases,
  onClaim,
  busyId,
}: {
  cases: Case[];
  onClaim?: (item: Case) => void;
  busyId?: string | null;
}) {
  return cases.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Investigation / account</th>
            <th>Priority</th>
            <th>Owner</th>
            <th>Channel</th>
            <th>Exposure</th>
            <th>Risk score</th>
            <th>Investigation</th>
            <th>Verdict</th>
            <th>Updated (IST)</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((item) => (
            <tr key={item.case_id}>
              <td>
                <CaseLink id={item.case_id} />
                <small className="record-sub">{item.account_id}</small>
              </td>
              <td>
                <div className="priority-cell" title={item.priority_reason}>
                  <strong className="numeric">{item.priority ?? "—"}</strong>
                  <span className="priority-bar" aria-hidden="true">
                    <span style={{ width: `${item.priority ?? 0}%` }} />
                  </span>
                </div>
              </td>
              <td>
                <Owner item={item} />
                {onClaim && !item.assignee && item.status !== "resolved" && (
                  <button
                    className="row-action"
                    disabled={busyId === item.case_id}
                    aria-label={`Claim ${item.case_id}`}
                    onClick={() => onClaim(item)}
                  >
                    Claim
                  </button>
                )}
              </td>
              <td>
                <ChannelLabel channel={item.channel} />
              </td>
              <td className="numeric">{money(item.amount_minor)}</td>
              <td>
                <div className="risk-cell">
                  <span className={`risk-score ${item.severity}`}>{(item.score * 100).toFixed(1)}</span>
                  <meter min="0" max="100" value={item.score * 100} aria-label="Risk score" />
                </div>
              </td>
              <td>
                <Status value={item.status} />
              </td>
              <td>
                <Status value={item.verdict} />
              </td>
              <td className="date-cell">{dateTime(item.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty>No investigations match this view. Generate a supported scenario in Transactions.</Empty>
  );
}
export function TransactionTable({ transactions }: { transactions: Transaction[] }) {
  return transactions.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Payment / account</th>
            <th>Channel</th>
            <th>Amount</th>
            <th>Risk</th>
            <th>Bank outcome</th>
            <th>Investigation</th>
            <th>Time (IST)</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((item) => (
            <tr key={item.txn_id}>
              <td>
                <span className="identifier">{item.txn_id}</span>
                <small className="record-sub">{item.account_id}</small>
              </td>
              <td>
                <ChannelLabel channel={item.channel} />
              </td>
              <td className="numeric">{money(item.amount_minor)}</td>
              <td className="numeric">{(item.score * 100).toFixed(1)}</td>
              <td>
                <Status value={item.payment_status} />
                {item.bank_reason && <small className="record-sub">{item.bank_reason}</small>}
              </td>
              <td>
                {item.case_id ? <CaseLink id={item.case_id} /> : <span className="muted">No alert</span>}
              </td>
              <td className="date-cell">{dateTime(item.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty>No payment attempts in this view.</Empty>
  );
}
export function Timeline({ events }: { events: AuditEvent[] }) {
  return events.length ? (
    <ol className="incident-timeline">
      {events.map((event) => (
        <li key={event.id}>
          <div className="timeline-meta">
            <time dateTime={event.occurred_at}>{dateTime(event.occurred_at)} IST</time>
            <span>
              #{event.id} · {event.actor}
            </span>
          </div>
          <div className="timeline-body">
            <strong>{human(event.event_type)}</strong>
            <p>{event.message}</p>
            {event.case_id && <CaseLink id={event.case_id} />}
          </div>
        </li>
      ))}
    </ol>
  ) : (
    <Empty>No events recorded yet.</Empty>
  );
}
