"use client";
import { Bank, ShieldCheck } from "@phosphor-icons/react";
import { type Snapshot, human, money } from "@/lib/operations";
import { useOperations } from "../OperationsProvider";
import { ActionLedger, CaseLink, Empty, Loading, PageHeading } from "../Primitives";

type Account = Snapshot["bank"]["accounts"][number];

/** Frozen, closed and liened accounts are listed first. */
function needsAttention(account: Account) {
  return account.status !== "active" || (account.liens?.length ?? 0) > 0;
}

function statusLabel(status: Account["status"]) {
  if (status === "frozen") return "Frozen";
  if (status === "closed") return "Closed";
  return "Active";
}

function AccountPositions({ accounts }: { accounts: Account[] }) {
  const sorted = [...accounts].sort((x, y) => Number(needsAttention(y)) - Number(needsAttention(x)));
  return (
    <section className="ops-section">
      <div className="section-heading">
        <div>
          <h2>Simulated account positions</h2>
          <p>
            Restrictions are owned by individual cases. Releasing one case preserves other active
            restrictions. Frozen, closed and liened accounts are listed first.
          </p>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th>Status</th>
              <th>Available / balance</th>
              <th>Liens</th>
              <th>Active restrictions</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((account) => (
              <tr key={account.account_id}>
                <td className="identifier">{account.account_id}</td>
                <td>
                  <span className={`account-status ${account.status}`}>{statusLabel(account.status)}</span>
                </td>
                <td className="numeric">
                  <strong>{money(account.available_minor)}</strong>
                  <small className="record-sub">of {money(account.balance_minor)}</small>
                </td>
                <td>
                  {account.liens?.length ? (
                    <ul className="lien-list">
                      {account.liens.map((lien) => (
                        <li key={lien.lien_id}>
                          <span className="numeric">{money(lien.amount_minor)}</span>{" "}
                          <CaseLink id={lien.case_id} />
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span className="muted">None</span>
                  )}
                </td>
                <td>{account.active_restrictions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!accounts.length && <Empty>No bank account positions available.</Empty>}
    </section>
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
      <div className="bank-status-board">
        <div className="bank-connection">
          <Bank size={30} aria-hidden="true" />
          <span>
            <small>Simulator connection</small>
            <strong className={snapshot.bank.connected ? "good" : "bad"}>
              {snapshot.bank.connected ? "Available" : "Unavailable"}
            </strong>
          </span>
        </div>
        <div>
          <small>Delivery mode</small>
          <strong>{human(snapshot.bank.mode)}</strong>
        </div>
        <div>
          <small>Awaiting acknowledgement</small>
          <strong>{snapshot.counts.pending_actions}</strong>
        </div>
        <div>
          <small>Failed deliveries</small>
          <strong className={snapshot.counts.failed_actions ? "bad" : ""}>
            {snapshot.counts.failed_actions}
          </strong>
        </div>
      </div>
      <div className="bank-process-note">
        <ShieldCheck size={18} />
        <p>
          A protective request becomes an enforced restriction only after the bank simulator acknowledges it.
          Failed deliveries can be retried below.
        </p>
      </div>
      {snapshot.bank.last_error && (
        <p className="form-error" role="alert">
          {snapshot.bank.last_error}
        </p>
      )}
      <section className="ops-section">
        <div className="section-heading">
          <h2>Restriction and release deliveries</h2>
          <span className="muted">Latest {snapshot.actions.length} actions</span>
        </div>
        <ActionLedger actions={snapshot.actions} />
      </section>
      <AccountPositions accounts={snapshot.bank.accounts} />
    </>
  );
}
