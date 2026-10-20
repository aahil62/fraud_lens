"use client";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle,
  Clock,
  CreditCard,
  ShieldCheck,
  WarningCircle,
} from "@phosphor-icons/react";
import { CHANNELS, type Snapshot, channelName, dateTime, human, money } from "@/lib/operations";
import { useOperations } from "../OperationsProvider";
import { Empty, Loading, PageHeading } from "../Primitives";
import { Timeline } from "../Records";

const BIN_COUNT = 6;
const BIN_MS = 5 * 60 * 1000;

function istTime(time: number) {
  return new Date(time).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  });
}

function activityBins(snapshot: Snapshot) {
  const end = new Date(snapshot.as_of).getTime();
  return Array.from({ length: BIN_COUNT }, (_, index) => {
    const start = end - (BIN_COUNT - index) * BIN_MS;
    const count = snapshot.transactions.filter((txn) => {
      const at = new Date(txn.timestamp).getTime();
      return at > start && at <= start + BIN_MS;
    }).length;
    return { start, count };
  });
}

function ActivityChart({ snapshot }: { snapshot: Snapshot }) {
  const bins = activityBins(snapshot);
  const max = Math.max(1, ...bins.map((bin) => bin.count));
  const total = bins.reduce((sum, bin) => sum + bin.count, 0);
  const summary = bins
    .map((bin) => `${istTime(bin.start)} to ${istTime(bin.start + BIN_MS)}: ${bin.count} attempts`)
    .join("; ");
  return (
    <section className="ops-section activity-chart-panel">
      <div className="section-heading">
        <div>
          <h2>Recent payment activity</h2>
          <p>Last 30 minutes · five-minute intervals · IST</p>
        </div>
        <span className="chart-total">
          <strong>{total}</strong> sampled attempts
        </span>
      </div>
      <div className="activity-chart" role="img" aria-label={summary}>
        <div className="activity-bars">
          {bins.map((bin, index) => (
            <div className="activity-column" key={bin.start} data-current={index === bins.length - 1}>
              <strong>{bin.count}</strong>
              <div className="activity-column-track">
                <span style={{ height: `${(bin.count / max) * 100}%` }} />
              </div>
              <time>{istTime(bin.start)}</time>
            </div>
          ))}
        </div>
      </div>
      <p className="chart-scope">
        Calculated from the latest {snapshot.transactions.length} transactions in this snapshot. Older records
        outside the snapshot are excluded.
      </p>
    </section>
  );
}

function ChannelChart({ snapshot }: { snapshot: Snapshot }) {
  const max = Math.max(1, ...snapshot.channels.map((row) => row.transactions));
  const summary = snapshot.channels
    .map((row) => `${channelName(row.channel)}: ${row.transactions} payment attempts`)
    .join("; ");
  return (
    <section className="ops-section channel-chart-panel">
      <div className="section-heading">
        <div>
          <h2>Payment channels</h2>
          <p>All recorded attempts, by channel</p>
        </div>
      </div>
      <div className="channel-chart" role="img" aria-label={summary}>
        {CHANNELS.map((channel) => {
          const row = snapshot.channels.find((item) => item.channel === channel);
          const count = row?.transactions ?? 0;
          return (
            <div className="channel-chart-row" key={channel}>
              <div>
                <strong>{channelName(channel)}</strong>
                <span>{count.toLocaleString("en-IN")}</span>
              </div>
              <div className="channel-bar-track">
                <span style={{ width: `${(count / max) * 100}%` }} />
              </div>
              <small>
                {row?.cases ?? 0} cases <span>·</span> {row?.pending_review ?? 0} awaiting review{" "}
                <span>·</span> {row?.resolved ?? 0} resolved <span>·</span> {row?.declined ?? 0} declined
              </small>
            </div>
          );
        })}
      </div>
      <Link href="/live" className="panel-footer-link">
        Explore transaction ledger <ArrowRight size={16} />
      </Link>
    </section>
  );
}

function OverviewMetrics({ snapshot }: { snapshot: Snapshot }) {
  const c = snapshot.counts;
  const metrics = [
    {
      label: "Payment attempts",
      value: c.transactions,
      detail: `${c.posted} posted · ${c.declined} declined`,
      icon: CreditCard,
    },
    {
      label: "Awaiting review",
      value: c.pending_review,
      detail: `${c.investigating} investigating · ${c.escalated} escalated`,
      icon: Clock,
    },
    {
      label: "Resolved cases",
      value: c.resolved,
      detail: `${c.confirmed_fraud} fraud · ${c.false_positives} false positives`,
      icon: CheckCircle,
    },
    {
      label: "Active restrictions",
      value: c.restricted_accounts + c.restricted_cards,
      detail: `${c.restricted_accounts} accounts · ${c.restricted_cards} cards`,
      icon: ShieldCheck,
    },
  ];
  return (
    <div className="overview-metrics">
      {metrics.map(({ label, value, detail, icon: Icon }) => (
        <div className="overview-metric" key={label}>
          <div>
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </div>
          <strong>{value.toLocaleString("en-IN")}</strong>
          <small>{detail}</small>
        </div>
      ))}
    </div>
  );
}

function PriorityList({ snapshot }: { snapshot: Snapshot }) {
  const rank = (item: Snapshot["cases"][number]) => item.priority ?? item.score * 100;
  const priority = snapshot.cases
    .filter((item) => item.status !== "resolved")
    .sort((a, b) => rank(b) - rank(a))
    .slice(0, 5);
  return (
    <section className="ops-section priority-panel">
      <div className="section-heading">
        <div>
          <h2>Next to investigate</h2>
          <p>Highest agent priority among the latest {snapshot.cases.length} cases</p>
        </div>
        <Link href="/cases" className="section-text-link">
          View queue <ArrowUpRight size={15} />
        </Link>
      </div>
      {priority.map((item) => (
        <Link
          key={item.case_id}
          className="focus-case-row"
          href={`/case?case_id=${encodeURIComponent(item.case_id)}`}
        >
          <span className={`risk-score ${item.severity}`}>{(item.score * 100).toFixed(1)}</span>
          <span className="focus-case-main">
            <strong>
              {item.account_id}
              <small>{channelName(item.channel)}</small>
            </strong>
            <span>{item.reasons[0] ?? "Review detection evidence"}</span>
            <small className="identifier">{item.case_id}</small>
          </span>
          <span className="focus-case-value">
            <strong>{money(item.amount_minor)}</strong>
            <small>{human(item.status)}</small>
          </span>
          <ArrowUpRight size={17} />
        </Link>
      ))}
      {!priority.length && <Empty>The investigation queue is clear. New alerts will appear here.</Empty>}
    </section>
  );
}

export function DashboardView() {
  const { snapshot } = useOperations();
  if (!snapshot) return <Loading />;
  const c = snapshot.counts;
  return (
    <div className="workspace-view dashboard-view">
      <PageHeading
        title="Your operations, in focus."
        description="Monitor payments and move the right investigations forward."
      >
        <Link href="/cases" className="primary-button">
          Review investigations <ArrowRight size={17} />
        </Link>
      </PageHeading>
      <OverviewMetrics snapshot={snapshot} />
      {(c.failed_actions > 0 || c.pending_actions > 0) && (
        <Link className="delivery-notice" href="/bank">
          <WarningCircle size={22} />
          <span>
            <strong>Bank deliveries need attention</strong>
            <small>
              {c.failed_actions} failed · {c.pending_actions} pending actions
            </small>
          </span>
          <span>
            Review deliveries <ArrowRight size={16} />
          </span>
        </Link>
      )}
      <div className="dashboard-charts">
        <ActivityChart snapshot={snapshot} />
        <ChannelChart snapshot={snapshot} />
      </div>
      <div className="dashboard-worklists">
        <PriorityList snapshot={snapshot} />
        <section className="ops-section recent-events-panel">
          <div className="section-heading">
            <div>
              <h2>Latest activity</h2>
              <p>Payments, protection and review</p>
            </div>
            <Link href="/audit" className="section-text-link">
              Audit trail <ArrowUpRight size={15} />
            </Link>
          </div>
          <Timeline events={snapshot.events.slice(0, 4)} />
        </section>
      </div>
      <div className="evidence-footnote">
        <ShieldCheck size={18} />
        <p>
          Synthetic local activity. Risk scores are signals, not probabilities. Real-bank performance and
          regulatory certification have not been established.
        </p>
        <time>Snapshot {dateTime(snapshot.as_of)} IST</time>
      </div>
    </div>
  );
}
