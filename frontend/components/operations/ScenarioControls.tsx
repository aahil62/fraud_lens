"use client";
import { useState } from "react";
import { CaretDown, Flask, Pause, Play, SlidersHorizontal } from "@phosphor-icons/react";
import { CHANNELS, channelName, type Channel } from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
export default function ScenarioControls() {
  const { snapshot, mutate } = useOperations();
  const [channel, setChannel] = useState<Channel>("upi");
  const [scenario, setScenario] = useState("fraud");
  const [interval, setIntervalValue] = useState(5);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function execute(path: string, body: unknown, success: string) {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await mutate(path, body);
      setMessage(success);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="scenario-desk">
      <div className="scenario-desk-heading">
        <Flask size={21} aria-hidden="true" /><h2>Simulation desk</h2><span>Test accounts only</span><p>Scenario labels are hidden from detection.</p>
      </div>
      <div className="scenario-command-strip">
        <form className="scenario-generate-form"
          onSubmit={(e) => {
            e.preventDefault();
            void execute(
              "/simulation/scenario",
              { channel, scenario },
              "Scenario submitted. Review its transactions and investigations below.",
            );
          }}
        >
          <div className="scenario-inputs">
            <label>
              Payment channel
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value as Channel)}
              >
                {CHANNELS.map((c) => (
                  <option key={c} value={c}>
                    {channelName(c)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Scenario
              <select
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
              >
                <option value="normal">Normal activity</option>
                <option value="fraud">Supported fraud pattern</option>
                <option value="false_positive">
                  Legitimate unusual activity
                </option>
                <option value="cross_channel">
                  Cross-channel incident (all four)
                </option>
                <option value="mule_layering">Mule layering (UPI → mules → ATM)</option>
                <option value="sim_swap_takeover">SIM-swap takeover (net banking)</option>
                <option value="card_testing">Card testing (cards)</option>
                <option value="atm_cashout">ATM cash-out burst</option>
              </select>
            </label>
          </div>
          <button className="primary-button" disabled={busy}>{busy ? "Processing…" : "Generate scenario"}<Play size={14} weight="fill" aria-hidden="true" /></button>
        </form>
        <div className="scenario-stream">
            <span>
              <strong>Continuous stream</strong>
              <small>
                {snapshot?.simulation_state.running ? "Running" : "Paused"} ·
                every {snapshot?.simulation_state.interval_seconds ?? "…"}{" "}
                seconds
              </small>
            </span>
            <button
              disabled={busy || !snapshot}
              onClick={() => {
                void execute(
                  "/simulation/control",
                  { running: !snapshot?.simulation_state.running },
                  "Stream control updated.",
                );
              }}
            >
              {snapshot?.simulation_state.running ? <Pause size={14} /> : <Play size={14} />}{snapshot?.simulation_state.running ? "Pause stream" : "Resume stream"}
            </button>
        </div>
      </div>
      <details className="scenario-advanced"><summary><SlidersHorizontal size={17} aria-hidden="true" />Stream & delivery settings<CaretDown size={15} aria-hidden="true" /></summary><div className="scenario-advanced-content">
          <form
            className="control-line"
            onSubmit={(e) => {
              e.preventDefault();
              void execute(
                "/simulation/control",
                { interval_seconds: interval },
                "Stream interval updated.",
              );
            }}
          >
            <label>
              Interval (seconds)
              <input
                type="number"
                min="2"
                max="60"
                required
                value={interval}
                onChange={(e) => setIntervalValue(Number(e.target.value))}
              />
            </label>
            <button disabled={busy}>Apply interval</button>
          </form>
        <div className="scenario-bank-control">
          <label>
            Bank delivery mode
            <select
              value={snapshot?.bank.mode ?? "normal"}
              disabled={busy}
              onChange={(e) => {
                void execute(
                  "/simulation/control",
                  { bank_mode: e.target.value },
                  "Bank mode changed. Existing acknowledgements remain authoritative.",
                );
              }}
            >
              <option value="normal">Normal responses</option>
              <option value="reject">Reject new requests</option>
              <option value="timeout_after_commit">
                Timeout after committing action
              </option>
            </select>
          </label>
          <p className="fine-print">
            Failure modes exercise pending requests, reconciliation and retries.
          </p>
        </div><div className="scenario-process"><button
            disabled={busy}
            onClick={() => {
              void execute(
                "/process",
                undefined,
                "Due jobs processed. Check the bank ledger for acknowledgements.",
              );
            }}
          >
            Process pending jobs
          </button>
        </div>
      </div></details>
      {message && (
        <p className="success-message" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
