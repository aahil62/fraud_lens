import Link from "next/link";
export default function Home() {
  return (
    <main className="landing">
      <header className="landing-nav">
        <Link className="landing-wordmark" href="/">
          FraudLens<span>Financial crime operations</span>
        </Link>
        <Link href="/login">Analyst sign in ↗</Link>
      </header>
      <section className="landing-composition">
        <div className="landing-title">
          <h1>
            Follow the evidence.
            <br />
            Close the loop.
          </h1>
          <p>
            A connected workspace for detecting suspicious payments, enforcing
            simulated protection, and investigating what happened.
          </p>
        </div>
        <div className="landing-channel-index">
          <span>UPI</span>
          <span>Net banking</span>
          <span>Cards</span>
          <span>ATMs</span>
        </div>
        <div
          className="landing-process"
          aria-label="FraudLens investigation workflow"
        >
          <div>
            <span>01</span>
            <strong>A payment arrives.</strong>
            <p>
              Signals are evaluated against observed history across four payment
              channels.
            </p>
          </div>
          <div>
            <span>02</span>
            <strong>Protection is requested.</strong>
            <p>
              A separate bank simulator acknowledges a restriction and enforces
              its scope.
            </p>
          </div>
          <div>
            <span>03</span>
            <strong>An analyst decides.</strong>
            <p>
              Evidence, connected accounts and the event timeline support a
              recorded verdict.
            </p>
          </div>
          <div>
            <span>04</span>
            <strong>Every view agrees.</strong>
            <p>
              Payments, cases and bank acknowledgements update from one
              operational ledger.
            </p>
          </div>
        </div>
        <div className="landing-entry">
          <Link className="primary-button" href="/login">
            Enter the simulation ↗
          </Link>
          <p>
            Local showcase · Synthetic transactions · No external bank
            connection
          </p>
        </div>
      </section>
      <footer className="landing-footer">
        <strong>Built to make decisions traceable.</strong>
        <p>
          FraudLens demonstrates supported detection scenarios and reversible
          protective actions. Synthetic evaluation is not real-world bank
          validation. Formal regulatory approval or certification is not
          claimed.
        </p>
        <a
          href="https://github.com/aahil62/fraud_lens"
          target="_blank"
          rel="noreferrer"
        >
          View the project ↗
        </a>
      </footer>
    </main>
  );
}
