"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle, ShieldCheck } from "@phosphor-icons/react";
import {
  type Case,
  type Decision,
  OperationsError,
  channelName,
  dateTime,
  decideCase,
  human,
  money,
  opsFetch,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import {
  ActionLedger,
  Empty,
  Loading,
  PageHeading,
  ReportButtons,
  Status,
  Timeline,
  TransactionTable,
} from "./Primitives";
import { EvidenceGraph } from "./EvidenceGraph";
export function DecisionPanel({
  item,
  onUpdated,
}: {
  item: Case;
  onUpdated: (item: Case) => void;
}) {
  const { refresh } = useOperations();
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const falsePositive = item.verdict === "false_positive";
  const resolved = item.status === "resolved";
  const canReverseFraud = resolved && item.verdict === "fraud";
  async function decide(action: Decision) {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const updated = await decideCase(
        item.case_id,
        action,
        item.version,
        notes,
      );
      onUpdated(updated);
      await refresh();
      setNotes("");
      setMessage(
        "Decision recorded. Bank-action acknowledgement determines the final resolution state.",
      );
    } catch (err) {
      setError(
        err instanceof OperationsError && err.status === 409
          ? "Another update changed this case. The latest record is being loaded. Review it before submitting again."
          : err instanceof Error
            ? err.message
            : "Decision failed.",
      );
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="decision-panel">
      <div className="section-heading">
        <div>
          <h2>Analyst decision</h2>
          <p>
            Case version {item.version}. Every decision carries your identity.
          </p>
        </div>
      </div>
      {falsePositive && <p className="fine-print" role="status">{resolved
        ? "False-positive verdict is final. This case no longer has a pending release."
        : "Release is awaiting bank confirmation. Decisions are locked; retry a failed release in Bank actions."}</p>}
      {canReverseFraud && <p className="fine-print">This fraud verdict is resolved. You can reverse it with documented evidence by marking a false positive and requesting release.</p>}
      <label>
        Investigation notes
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          maxLength={3000}
          rows={4}
          placeholder="Explain the evidence behind your decision. Required for a fraud or false-positive verdict."
        />
      </label>
      <div className="decision-actions">
        <button
          disabled={busy || resolved || falsePositive}
          onClick={() => {
            void decide("investigate");
          }}
        >
          Start investigation
        </button>
        <button
          disabled={busy || resolved || falsePositive}
          onClick={() => {
            void decide("escalate");
          }}
        >
          Escalate
        </button>
        <button
          className="danger-button"
          disabled={busy || resolved || falsePositive || !notes.trim()}
          onClick={() => {
            void decide("confirm_fraud");
          }}
        >
          Confirm fraud
        </button>
        <button
          className="primary-button"
          disabled={busy || falsePositive || (resolved && !canReverseFraud) || !notes.trim()}
          onClick={() => {
            void decide("false_positive");
          }}
        >
          Mark false positive & release
        </button>
      </div>
      <p className="fine-print">
        A false-positive verdict requests release of this case’s restriction. It
        cannot remove restrictions owned by another case.
      </p>
      {busy && <p role="status">Recording decision…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="success-message" role="status">
          {message}
        </p>
      )}
    </section>
  );
}
export default function CaseWorkspace({ caseId }: { caseId: string }) {
  const { snapshot } = useOperations();
  const [item, setItem] = useState<Case | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!caseId) return;
    let active = true;
    void opsFetch<Case>(`/cases/${encodeURIComponent(caseId)}`)
      .then((value) => {
        if (active) {
          setItem(value);
          setError("");
        }
      })
      .catch((err) => {
        if (active)
          setError(err instanceof Error ? err.message : "Case unavailable.");
      });
    return () => {
      active = false;
    };
  }, [caseId, snapshot?.cursor]);
  if (!caseId)
    return (
      <>
        <PageHeading
          title="Investigation workspace"
          description="Choose a case to inspect evidence and record a decision."
        />
        <Empty>
          <Link href="/cases">Open the investigation queue →</Link>
        </Empty>
      </>
    );
  if (error && !item)
    return (
      <>
        <PageHeading title="Case unavailable" description={error} />
        <Link href="/cases">Return to investigations →</Link>
      </>
    );
  if (!item) return <Loading />;
  const latestAction = [...item.actions]
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .at(-1);
  return (
    <>
      <div className="case-back">
          <Link href="/cases"><ArrowLeft size={12}/>Investigation queue</Link>
        <span>Updated {dateTime(item.updated_at)} IST</span>
      </div>
      <PageHeading
        title={`${channelName(item.channel)} investigation`}
        description={`${item.case_id} · ${item.account_id} · ${money(item.amount_minor)}`}
      >
        <ReportButtons caseId={item.case_id} />
      </PageHeading>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="case-state-strip">
        <div>
          <span>Investigation</span>
          <Status value={item.status} />
        </div>
        <div>
          <span>Analyst verdict</span>
          <Status value={item.verdict} />
        </div>
        <div>
          <span>Detection score</span>
          <strong className={`risk-score ${item.severity}`}>
            {(item.score * 100).toFixed(1)} / 100
          </strong>
        </div>
        <div>
          <span>Protection</span>
          <strong>
            {latestAction
              ? `${latestAction.operation === "release" ? "Release" : "Restriction"} ${latestAction.status}`
              : "No action recorded"}
          </strong>
        </div>
      </div>
      <section className="recommendation">
        <strong>
          {item.status === "resolved" ? <CheckCircle size={18} weight="duotone"/> : <ShieldCheck size={18} weight="duotone"/>}
          {item.verdict === "false_positive"
            ? item.status === "resolved" ? "False positive resolved" : "Awaiting release acknowledgement"
            : item.verdict === "fraud"
              ? "Fraud confirmed by analyst"
              : "Review the detected pattern"}
        </strong>
        <p>
          {item.verdict === "unreviewed"
            ? "Automated detection is a signal. Investigate the triggering evidence and account history before recording a verdict."
            : item.notes ||
              "Check delivery status and the case timeline for the latest outcome."}
        </p>
      </section>
      <div className="case-columns">
        <div>
          <section className="ops-section">
            <div className="section-heading">
              <div>
                <h2>Why this payment was flagged</h2>
                <p>Detection reasons and individual signal contributions.</p>
              </div>
            </div>
            <ul className="reason-list">
              {item.reasons.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
            <div className="signal-list">
              {item.signals.map((signal, i) => (
                <div key={`${signal.name}-${i}`}>
                  <div>
                    <strong>{human(signal.name)}</strong>
                    <span className="numeric">
                      {(signal.score * 100).toFixed(1)}
                    </span>
                  </div>
                  <meter
                    min="0"
                    max="100"
                    value={signal.score * 100}
                    aria-label={`${signal.name} score`}
                  />
                  {signal.reasons.length > 0 && (
                    <p>{signal.reasons.join(" · ")}</p>
                  )}
                </div>
              ))}
            </div>
          </section>
          <DecisionPanel key={item.case_id} item={item} onUpdated={setItem} />
          <section className="ops-section">
            <div className="section-heading">
              <h2>Bank actions</h2>
            </div>
            <ActionLedger actions={item.actions} />
          </section>
          <section className="ops-section">
            <div className="section-heading">
              <h2>Related payment attempts</h2>
            </div>
            <TransactionTable transactions={item.related_transactions} />
          </section>
        </div>
        <div>
          <section className="ops-section">
            <div className="section-heading">
              <h2>Evidence connections</h2>
            </div>
            <EvidenceGraph cases={[item]} />
            <p className="fine-print graph-caption">
              Connections show shared account, beneficiary or instrument
              identifiers present in the case evidence.
            </p>
          </section>
          <section className="ops-section">
            <div className="section-heading">
              <div>
                <h2>Incident timeline</h2>
                <p>Payment → protection → analyst review</p>
              </div>
            </div>
            <Timeline events={[...item.timeline].sort((a, b) => a.id - b.id)} />
          </section>
        </div>
      </div>
    </>
  );
}
