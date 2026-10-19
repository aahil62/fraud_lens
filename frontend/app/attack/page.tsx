"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Bank, CheckCircle, CreditCard, Money, ShieldWarning, SimCard, Circle } from "@phosphor-icons/react";
import { AttackError, getAttack, launchAttack, reportTo1930, type AttackStatus, type Typology } from "@/lib/attacks";
import "./attack.css";
const SCAMS: { id: Typology; name: string; description: string; icon: typeof Bank }[] = [
  { id: "mule_layering", name: "Mule layering", icon: Bank,
    description: "A victim is tricked into a UPI payment; the money hops through mule accounts and is withdrawn at an ATM." },
  { id: "sim_swap_takeover", name: "SIM-swap takeover", icon: SimCard,
    description: "An attacker ports the victim's number, fails a few logins, then moves a large sum from a new device." },
  { id: "card_testing", name: "Card testing", icon: CreditCard,
    description: "Small charges probe a stolen card before one big purchase." },
  { id: "atm_cashout", name: "ATM cash-out", icon: Money,
    description: "Rapid withdrawals across several ATMs on one card." },
];
const POLL_MS = 1500;
const POLL_LIMIT_MS = 120000;
const rupees = (minor: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(minor / 100);
export default function AttackPage() {
  const [typology, setTypology] = useState<Typology>("mule_layering");
  const [amount, setAmount] = useState(48000);
  const [attackId, setAttackId] = useState<string | null>(null);
  const [status, setStatus] = useState<AttackStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const pollStarted = useRef(0);
  useEffect(() => {
    if (!attackId || !polling) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const next = await getAttack(attackId);
        if (cancelled) return;
        setStatus(next);
        if (next.outcome !== "in_progress" || Date.now() - pollStarted.current > POLL_LIMIT_MS) {
          setPolling(false);
          return;
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Status unavailable.");
      }
      if (!cancelled) timer = setTimeout(() => { void tick(); }, POLL_MS);
    };
    void tick();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [attackId, polling]);
  function startPolling() {
    pollStarted.current = Date.now();
    setPolling(true);
  }
  async function launch() {
    setBusy(true);
    setError("");
    setStatus(null);
    setPolling(false);
    try {
      const result = await launchAttack(typology, amount * 100);
      setAttackId(result.attack_id);
      startPolling();
    } catch (err) {
      setError(err instanceof AttackError ? err.message : "Launch failed. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function report() {
    if (!attackId) return;
    setBusy(true);
    setError("");
    try {
      setStatus(await reportTo1930(attackId));
      startPolling();
    } catch (err) {
      setError(err instanceof AttackError ? err.message : "Report failed. Try again.");
    } finally {
      setBusy(false);
    }
  }
  const flagged = status?.steps[1]?.status === "done";
  const canReport = status?.typology === "mule_layering" && (flagged || !polling);
  return <div className="attack-page">
    <header className="attack-header">
      <span className="attack-brand">FraudLens · Attack console</span>
      <span className="attack-chip">Fictional money only</span>
    </header>
    <main>
      <h1>Launch a scam. Watch the bank react.</h1>
      <p className="attack-lede">Every payment here is fictional and runs against a simulated bank. Analysts on the FraudLens console see it arrive in real time.</p>
      <fieldset className="attack-scams" disabled={busy}>
        <legend>Step 1 · Pick a scam</legend>
        {SCAMS.map(({ id, name, description, icon: Icon }) => <label key={id} className="attack-scam" data-selected={typology === id}>
          <input type="radio" name="typology" value={id} checked={typology === id} onChange={() => setTypology(id)} />
          <Icon size={22} weight="duotone" aria-hidden="true" />
          <span><strong>{name}</strong><small>{description}</small></span>
        </label>)}
      </fieldset>
      {typology === "mule_layering" && <label className="attack-amount">
        <span>Scam amount <strong>{rupees(amount * 100)}</strong></span>
        <input type="range" min={1000} max={200000} step={1000} value={amount}
          aria-label="Scam amount in rupees" aria-valuetext={rupees(amount * 100)}
          onChange={(e) => setAmount(Number(e.target.value))} />
        <span className="attack-range"><small>₹1,000</small><small>₹2,00,000</small></span>
      </label>}
      <button className="attack-launch" disabled={busy} onClick={() => { void launch(); }}>{busy && !status ? "Launching…" : "Launch attack"}<ArrowRight size={16} aria-hidden="true" /></button>
      {error && <p className="attack-error" role="alert">{error}</p>}
      {status && <section className="attack-timeline" aria-live="polite" aria-label="What happened">
        <h2>What happened {status.case_id_masked && <small>Case {status.case_id_masked}</small>}</h2>
        <ol>{status.steps.map((step) => <li key={step.label} data-status={step.status}>
          <span className="attack-step-icon" aria-hidden="true">{step.status === "done" ? <CheckCircle size={20} weight="fill" /> : step.status === "blocked" ? <ShieldWarning size={20} weight="fill" /> : <Circle size={20} />}</span>
          <span>{step.label}<small>{step.status === "done" ? "Done" : step.status === "blocked" ? "Blocked" : "Waiting"}{step.at ? ` · ${new Date(step.at).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" })} IST` : ""}</small></span>
        </li>)}</ol>
        {status.outcome !== "in_progress" && <p className="attack-outcome">{status.outcome === "caught" ? "Caught: an analyst confirmed fraud and the bank held the money." : status.outcome === "partially_caught" ? "Partly caught: fraud confirmed, but some money left before it could be held." : "Missed: this one got through."}</p>}
        {status.outcome === "in_progress" && !polling && <p className="attack-note">Still waiting for an analyst. The case stays open on the console.</p>}
        {canReport && !status.complaint_id && <button className="attack-report" disabled={busy} onClick={() => { void report(); }}>Report it to 1930 as the victim</button>}
        {status.complaint_id && <p className="attack-complaint" role="status">Complaint {status.complaint_id} filed. FraudLens traced {rupees(status.traced_total_minor)} and held {rupees(status.held_total_minor)}.</p>}
      </section>}
    </main>
    <footer className="attack-footer">Analysts are watching this live at /dashboard · <Link href="/login">Open the operations centre</Link></footer>
  </div>;
}
