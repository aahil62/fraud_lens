"use client";
import { useState } from "react";
import { type BankAction, human } from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { CaseLink, Empty, Status } from "./Primitives";

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
                    <small className="record-sub identifier">{action.target_id}</small>
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
                    <small className="record-sub identifier">{action.action_id}</small>
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
                        {busy === action.action_id ? "Retrying…" : "Retry action"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>No bank actions yet. Requests and confirmations appear here separately.</Empty>
      )}
    </>
  );
}
