"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CHANNELS,
  type Case,
  type Transaction,
  type Guidance,
  channelName,
  dateTime,
  human,
  money,
  opsFetch,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import {
  ActionLedger,
  CaseTable,
  Empty,
  Loading,
  PageHeading,
  ReportButtons,
  Timeline,
  TransactionTable,
} from "./Primitives";
import ScenarioControls from "./ScenarioControls";
export function DashboardView() {
  const { snapshot } = useOperations();
  if (!snapshot) return <Loading />;
  const c = snapshot.counts;
  return (
    <>
      <PageHeading
        title="Operations overview"
        description="One ledger. Every payment, protective action and analyst decision."
      >
        <Link href="/cases" className="primary-button">
          Open investigation queue
        </Link>
      </PageHeading>
      <div className="metric-strip">
        {[
          [
            "Payment attempts",
            c.transactions,
            `${c.posted} posted · ${c.declined} declined · ${c.pending_payments} pending`,
          ],
          [
            "Awaiting review",
            c.pending_review,
            `${c.investigating} investigating · ${c.escalated} escalated`,
          ],
          [
            "Resolved cases",
            c.resolved,
            `${c.confirmed_fraud} confirmed fraud · ${c.false_positives} false positives`,
          ],
          [
            "Active restrictions",
            c.restricted_accounts + c.restricted_cards,
            `${c.restricted_accounts} accounts · ${c.restricted_cards} cards`,
          ],
        ].map(([label, value, detail]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{Number(value).toLocaleString("en-IN")}</strong>
            <small>{detail}</small>
          </div>
        ))}
      </div>
      {(c.failed_actions > 0 || c.pending_actions > 0) && (
        <Link className="attention-line" href="/bank">
          <strong>
            {c.failed_actions} failed · {c.pending_actions} pending bank actions
          </strong>
          <span>Review delivery and acknowledgement →</span>
        </Link>
      )}
      <section className="ops-section">
        <div className="section-heading">
          <div>
            <h2>Coverage across payment channels</h2>
            <p>
              Database totals, updated with the shared operational snapshot.
            </p>
          </div>
          <Link href="/live">Inspect payments →</Link>
        </div>
        <div className="channel-ledger">
          <div className="channel-ledger-header">
            <span>Channel</span>
            <span>Payments</span>
            <span>Cases</span>
            <span>Awaiting review</span>
            <span>Resolved</span>
            <span>Declined</span>
          </div>
          {snapshot.channels.map((row) => (
            <div className="channel-ledger-row" key={row.channel}>
              <strong>{channelName(row.channel)}</strong>
              <span>{row.transactions}</span>
              <span>{row.cases}</span>
              <span>{row.pending_review}</span>
              <span>{row.resolved}</span>
              <span>{row.declined}</span>
            </div>
          ))}
        </div>
      </section>
      <div className="overview-split">
        <section className="ops-section">
          <div className="section-heading">
            <div>
              <h2>Investigation priority</h2>
              <p>Highest scores among the latest 200 cases.</p>
            </div>
          </div>
          {snapshot.cases
            .filter((x) => x.status !== "resolved")
            .sort((a, b) => b.score - a.score)
            .slice(0, 5)
            .map((item) => (
              <Link
                key={item.case_id}
                className="priority-row"
                href={`/case?case_id=${encodeURIComponent(item.case_id)}`}
              >
                <span className={`risk-score ${item.severity}`}>
                  {(item.score * 100).toFixed(1)}
                </span>
                <span>
                  <strong>{item.account_id}</strong>
                  <small>
                    {channelName(item.channel)} ·{" "}
                    {item.reasons[0] ?? "Review detection evidence"}
                  </small>
                </span>
                <span>
                  {money(item.amount_minor)}
                  <small>{human(item.status)}</small>
                </span>
              </Link>
            ))}
          {!snapshot.cases.some((x) => x.status !== "resolved") && (
            <Empty>The investigation queue is clear.</Empty>
          )}
        </section>
        <section className="ops-section">
          <div className="section-heading">
            <div>
              <h2>Latest operational events</h2>
              <p>Payment, protection and review in one sequence.</p>
            </div>
          </div>
          <Timeline events={snapshot.events.slice(0, 5)} />
        </section>
      </div>
      <section className="boundary-note">
        <strong>Evidence boundary</strong>
        <p>
          These figures describe synthetic local activity. Detection scores are
          risk signals, not probabilities. Real-bank performance and regulatory
          certification have not been established.
        </p>
      </section>
    </>
  );
}
export function LedgerView({ kind }: { kind: "cases" | "transactions" }) {
  const { snapshot } = useOperations();
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{
    items: Case[] | Transaction[];
    total: number;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ limit: "25", offset: String(offset) });
    if (channel) params.set("channel", channel);
    if (status && kind === "cases") params.set("status", status);
    void opsFetch<{ items: Case[] | Transaction[]; total: number }>(
      `/${kind}?${params}`,
    )
      .then((value) => {
        if (!cancelled) {
          setData(value);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Could not load ledger.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [kind, channel, status, offset, snapshot?.cursor]);
  return (
    <>
      <PageHeading
        title={kind === "cases" ? "Investigation queue" : "Transaction ledger"}
        description={
          kind === "cases"
            ? "Review evidence, make a verdict, and track its protective action."
            : "Continuous attempted payments and the bank simulator’s actual outcomes."
        }
      />
      {kind === "transactions" && <ScenarioControls />}
      <section className="ops-section">
        <div className="filter-bar">
          <label>
            Channel
            <select
              value={channel}
              onChange={(e) => {
                setChannel(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All channels</option>
              {CHANNELS.map((c) => (
                <option key={c} value={c}>
                  {channelName(c)}
                </option>
              ))}
            </select>
          </label>
          {kind === "cases" && (
            <label>
              Case status
              <select
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All statuses</option>
                {["new", "investigating", "escalated", "resolved"].map((s) => (
                  <option key={s} value={s}>
                    {human(s)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p>
            {data
              ? `${data.total.toLocaleString("en-IN")} matching records`
              : "Loading records…"}
          </p>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {!data ? (
          <Loading />
        ) : kind === "cases" ? (
          <CaseTable cases={data.items as Case[]} />
        ) : (
          <TransactionTable transactions={data.items as Transaction[]} />
        )}
        <div className="pagination">
          <span>
            {data?.total
              ? `${offset + 1}–${Math.min(offset + 25, data.total)} of ${data.total}`
              : "0 records"}
          </span>
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 25))}
          >
            Previous
          </button>
          <button
            disabled={!data || offset + 25 >= data.total}
            onClick={() => setOffset(offset + 25)}
          >
            Next
          </button>
        </div>
      </section>
    </>
  );
}
export function BankView() {
  const { snapshot } = useOperations();
  if (!snapshot) return <Loading />;
  return (
    <>
      <PageHeading
        title="Bank action ledger"
        description="A request is not an enforced restriction. Confirmation comes from the separate bank simulator."
      />
      <div className="bank-summary">
        <span>
          Simulator connection{" "}
          <strong className={snapshot.bank.connected ? "good" : "bad"}>
            {snapshot.bank.connected ? "Available" : "Unavailable"}
          </strong>
        </span>
        <span>
          Mode <strong>{human(snapshot.bank.mode)}</strong>
        </span>
        <span>
          Pending <strong>{snapshot.counts.pending_actions}</strong>
        </span>
        <span>
          Failed <strong>{snapshot.counts.failed_actions}</strong>
        </span>
      </div>
      {snapshot.bank.last_error && (
        <p className="form-error" role="alert">
          {snapshot.bank.last_error}
        </p>
      )}
      <section className="ops-section">
        <div className="section-heading">
          <h2>Restriction and release deliveries</h2>
          <span className="muted">
            Latest {snapshot.actions.length} actions
          </span>
        </div>
        <ActionLedger actions={snapshot.actions} />
      </section>
      <section className="ops-section">
        <div className="section-heading">
          <div>
            <h2>Simulated account positions</h2>
            <p>
              Restrictions are owned by individual cases. Releasing one case
              preserves other active restrictions.
            </p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Balance</th>
                <th>Account restriction</th>
                <th>Active restrictions</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.bank.accounts.map((account) => (
                <tr key={account.account_id}>
                  <td className="identifier">{account.account_id}</td>
                  <td className="numeric">{money(account.balance_minor)}</td>
                  <td>
                    {account.restricted
                      ? "Restricted"
                      : "No account restriction"}
                  </td>
                  <td>{account.active_restrictions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!snapshot.bank.accounts.length && (
          <Empty>No bank account positions available.</Empty>
        )}
      </section>
    </>
  );
}
export function AuditView() {
  const { snapshot } = useOperations();
  const [query, setQuery] = useState("");
  if (!snapshot) return <Loading />;
  const events = snapshot.events.filter((x) =>
    `${x.event_type} ${x.message} ${x.case_id} ${x.actor}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <>
      <PageHeading
        title="Audit trail"
        description="Persisted event history with authenticated actors and ordered event identifiers."
      />
      <section className="ops-section">
        <div className="filter-bar">
          <label>
            Search recent events
            <input
              placeholder="Case, event, message or analyst"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <p>Latest {snapshot.events.length} events · all times IST</p>
        </div>
        <Timeline events={events} />
      </section>
    </>
  );
}
export function ReportsView() {
  const { snapshot } = useOperations();
  if (!snapshot) return <Loading />;
  return (
    <>
      <PageHeading
        title="Investigation reports"
        description="Export timestamped evidence, decisions and bank acknowledgements from the current case record."
      />
      <section className="ops-section">
        <div className="section-heading">
          <h2>Recent investigations</h2>
          <Link href="/cases">Find any case →</Link>
        </div>
        {snapshot.cases.map((item) => (
          <div key={item.case_id} className="report-row">
            <div>
              <Link
                className="record-link"
                href={`/case?case_id=${encodeURIComponent(item.case_id)}`}
              >
                {item.case_id}
              </Link>
              <p>
                {channelName(item.channel)} · {human(item.verdict)} · version{" "}
                {item.version}
              </p>
              <small className="muted">
                Updated {dateTime(item.updated_at)} IST
              </small>
            </div>
            <ReportButtons caseId={item.case_id} />
          </div>
        ))}
        {!snapshot.cases.length && (
          <Empty>Open a case before exporting an investigation report.</Empty>
        )}
      </section>
      <p className="fine-print">
        Reports capture a point in time; later decisions do not alter an already
        downloaded report. For older cases, use the paginated investigation
        queue.
      </p>
    </>
  );
}
export function GuidanceView() {
  const { snapshot } = useOperations();
  const [guidance, setGuidance] = useState<Guidance | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void opsFetch<Guidance>("/guidance")
      .then((data) => {
        if (active) setGuidance(data);
      })
      .catch((err) => {
        if (active)
          setError(
            err instanceof Error ? err.message : "Guidance unavailable.",
          );
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <PageHeading
        title="Controls & guidance"
        description="Source-linked applicability and implemented controls. Alignment requires evidence, not a badge."
      />
      <section className="boundary-note">
        <strong>Scope and limitations</strong>
        <p>
          {guidance?.disclaimer ??
            "Local synthetic showcase. Formal NPCI approval, regulatory certification and real-bank validation are not claimed."}
        </p>
      </section>
      <section className="ops-section">
        <div className="section-heading">
          <div>
            <h2>Detection coverage</h2>
            <p>
              Version {snapshot?.detection.version ?? "…"}. Transparent scenario
              coverage is not real-world accuracy.
            </p>
          </div>
        </div>
        <div className="coverage-list">
          {snapshot?.detection.coverage.map((row, i) => (
            <div key={i}>
              {Object.entries(row).map(([key, value]) => (
                <p key={key}>
                  <strong>{human(key)}: </strong>
                  {Array.isArray(value)
                    ? value.join(" · ")
                    : typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value)}
                </p>
              ))}
            </div>
          ))}
        </div>
      </section>
      <section className="ops-section">
        <div className="section-heading">
          <h2>Requirements-to-evidence matrix</h2>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {guidance ? (
          <div className="guidance-list">
            {guidance.references.map((row) => (
              <article key={row.id}>
                <div>
                  <a href={row.source_url} target="_blank" rel="noreferrer">
                    {row.title} ↗
                  </a>
                  <small>
                    {row.source_date} · {row.status}
                  </small>
                </div>
                <dl>
                  <dt>Applicability</dt>
                  <dd>{row.applicability}</dd>
                  <dt>Control</dt>
                  <dd>{row.control}</dd>
                  <dt>Evidence</dt>
                  <dd>{row.test_evidence.join("; ") || "Not yet verified"}</dd>
                </dl>
              </article>
            ))}
          </div>
        ) : (
          !error && <Loading />
        )}
      </section>
    </>
  );
}
