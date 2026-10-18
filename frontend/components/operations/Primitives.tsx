"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowsLeftRight, Bank, CreditCard, DownloadSimple, Tray, Money } from "@phosphor-icons/react";
import {
  type AuditEvent,
  type BankAction,
  type Case,
  type Transaction,
  channelName,
  dateTime,
  exportReport,
  human,
  money,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
export function PageHeading({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  );
}
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty-state"><Tray size={28} weight="duotone"/>{children}</div>;
}
export function Loading() {
  return (
    <div className="loading-skeleton" role="status">
      <span aria-hidden="true"/><span aria-hidden="true"/><span aria-hidden="true"/><span aria-hidden="true"/>
      <p className="sr-only">Loading the operational ledger…</p>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  const risk = ["failed", "fraud", "critical", "high", "declined"].includes(
    value,
  )
    ? "bad"
    : ["confirmed", "resolved", "posted", "released"].includes(value)
      ? "good"
      : "";
  return <span className={`status ${value} ${risk}`}>{human(value)}</span>;
}
export function ChannelLabel({channel}:{channel:string}) {
  const Icon = channel === "upi" ? ArrowsLeftRight : channel === "net_banking" ? Bank : channel === "card" ? CreditCard : Money;
  return <span className="channel-label"><Icon size={15} weight="duotone"/>{channelName(channel)}</span>;
}
export function CaseLink({ id }: { id: string }) {
  return (
    <Link
      className="record-link"
      href={`/case?case_id=${encodeURIComponent(id)}`}
    >
      {id}
    </Link>
  );
}
export function CaseTable({ cases }: { cases: Case[] }) {
  return cases.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Investigation / account</th>
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
              <td><ChannelLabel channel={item.channel}/></td>
              <td className="numeric">{money(item.amount_minor)}</td>
              <td>
                <div className="risk-cell"><span className={`risk-score ${item.severity}`}>
                  {(item.score * 100).toFixed(1)}
                </span><meter min="0" max="100" value={item.score*100} aria-label="Risk score"/></div>
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
    <Empty>
      No investigations match this view. Generate a supported scenario in
      Transactions.
    </Empty>
  );
}
export function TransactionTable({
  transactions,
}: {
  transactions: Transaction[];
}) {
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
              <td><ChannelLabel channel={item.channel}/></td>
              <td className="numeric">{money(item.amount_minor)}</td>
              <td className="numeric">{(item.score * 100).toFixed(1)}</td>
              <td>
                <Status value={item.payment_status} />
                {item.bank_reason && (
                  <small className="record-sub">{item.bank_reason}</small>
                )}
              </td>
              <td>
                {item.case_id ? (
                  <CaseLink id={item.case_id} />
                ) : (
                  <span className="muted">No alert</span>
                )}
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
            <time dateTime={event.occurred_at}>
              {dateTime(event.occurred_at)} IST
            </time>
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
export function ActionLedger({ actions }: { actions: BankAction[] }) {
  const { mutate } = useOperations();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  async function retry(id: string) {
    setBusy(id);
    setError("");
    try {
      await mutate(`/actions/${encodeURIComponent(id)}/retry`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed.");
    } finally {
      setBusy(null);
    }
  }
  return (
    <>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {actions.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Operation / target</th>
                <th>Case</th>
                <th>Delivery</th>
                <th>Bank reference / error</th>
                <th>Attempts</th>
                <th>Recovery</th>
              </tr>
            </thead>
            <tbody>
              {actions.map((action) => (
                <tr key={action.action_id}>
                  <td>
                    <strong>
                      {human(action.operation)} {action.target_type}
                    </strong>
                    <small className="record-sub identifier">
                      {action.target_id}
                    </small>
                  </td>
                  <td>
                    <CaseLink id={action.case_id} />
                  </td>
                  <td>
                    <Status value={action.status} />
                  </td>
                  <td className="wrap-cell">
                    {action.last_error ? (
                      <span className="bad">{action.last_error}</span>
                    ) : (
                      (action.bank_reference ?? "Awaiting acknowledgement")
                    )}
                    <small className="record-sub identifier">
                      {action.action_id}
                    </small>
                  </td>
                  <td className="numeric">{action.attempts}</td>
                  <td>
                    {action.status === "failed" && (
                      <button
                        disabled={busy !== null}
                        onClick={() => {
                          void retry(action.action_id);
                        }}
                      >
                        {busy === action.action_id
                          ? "Retrying…"
                          : "Retry action"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>
          No bank actions yet. Requests and confirmations appear here
          separately.
        </Empty>
      )}
    </>
  );
}
export function ReportButtons({ caseId }: { caseId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function download(format: "json" | "markdown" | "pdf") {
    setBusy(true);
    setError("");
    try {
      await exportReport(caseId, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="button-row">
        {(["pdf", "markdown", "json"] as const).map((format) => (
          <button
            key={format}
            aria-label={`Download ${format.toUpperCase()} report for ${caseId}`}
            disabled={busy}
            onClick={() => {
              void download(format);
            }}
          >
            {format === "pdf" && <DownloadSimple size={13}/>} {format === "markdown" ? "MD" : format.toUpperCase()}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </div>
  );
}
