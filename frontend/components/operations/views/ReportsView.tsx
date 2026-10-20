"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, FileText, MagnifyingGlass } from "@phosphor-icons/react";
import { channelName, dateTime, human } from "@/lib/operations";
import { useOperations } from "../OperationsProvider";
import { Empty, Loading, PageHeading, ReportButtons } from "../Primitives";

export function ReportsView() {
  const { snapshot } = useOperations();
  const [query, setQuery] = useState("");
  const [verdict, setVerdict] = useState("");
  if (!snapshot) return <Loading />;
  const needle = query.toLowerCase();
  const reports = snapshot.cases.filter((item) => {
    const text = `${item.case_id} ${item.account_id} ${channelName(item.channel)}`.toLowerCase();
    return text.includes(needle) && (!verdict || item.verdict === verdict);
  });
  const verdicts = [...new Set(snapshot.cases.map((item) => item.verdict))];
  const emptyMessage = snapshot.cases.length
    ? "No recent case records match your search. Try another account or clear the filters."
    : "Open a case before exporting an investigation report.";
  return (
    <div className="workspace-view reports-view">
      <PageHeading
        title="Investigation reports"
        description="A portable record of the evidence, decisions and bank acknowledgements."
      >
        <Link href="/cases" className="secondary-button">
          Find an investigation <ArrowUpRight size={16} />
        </Link>
      </PageHeading>
      <div className="report-library-intro">
        <FileText size={32} aria-hidden="true" />
        <div>
          <h2>Your evidence library</h2>
          <p>Export a case as PDF for review, Markdown for notes, or JSON for structured evidence.</p>
        </div>
        <span>
          <strong>{snapshot.cases.length}</strong> recent case records
        </span>
      </div>
      <section className="ops-section report-library">
        <div className="filter-bar">
          <label className="search-field">
            Search recent case records
            <span>
              <MagnifyingGlass size={18} aria-hidden="true" />
              <input
                placeholder="Case ID, account or channel"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </span>
          </label>
          <label>
            Verdict
            <select value={verdict} onChange={(e) => setVerdict(e.target.value)}>
              <option value="">All verdicts</option>
              {verdicts.map((value) => (
                <option key={value} value={value}>
                  {human(value)}
                </option>
              ))}
            </select>
          </label>
          <p aria-live="polite">{reports.length} matching records</p>
        </div>
        {reports.map((item) => (
          <article key={item.case_id} className="library-report-row">
            <FileText size={23} aria-hidden="true" />
            <div className="library-report-main">
              <Link className="record-link" href={`/case?case_id=${encodeURIComponent(item.case_id)}`}>
                {item.case_id}
              </Link>
              <p>
                {item.account_id} · {channelName(item.channel)}
              </p>
            </div>
            <div className="library-report-meta">
              <strong>{human(item.verdict)}</strong>
              <small>
                Version {item.version} · {dateTime(item.updated_at)} IST
              </small>
            </div>
            <ReportButtons caseId={item.case_id} />
          </article>
        ))}
        {!reports.length && <Empty>{emptyMessage}</Empty>}
      </section>
      <p className="fine-print report-library-note">
        Reports capture a point in time. Later decisions do not alter a downloaded report. This library shows
        the latest {snapshot.cases.length} cases; use the investigation queue to find older records.
      </p>
    </div>
  );
}
