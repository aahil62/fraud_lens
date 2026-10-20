import Link from "next/link";
import { ArrowRight, ArrowUpRight, GithubLogo } from "@phosphor-icons/react";
import { LensMark } from "../../console/LensMark";

/** The ending resolves on the same graphite as the hero, and the footer sits on that floor. */
export function Close() {
  return (
    <div className="fl-ending">
      <section className="fl-close fl-section" data-sc-act="flow" aria-labelledby="close-heading">
        <div className="fl-close-statement">
          <LensMark />
          <h2 id="close-heading">
            Less guesswork.
            <br />
            <span>More clarity.</span>
          </h2>
          <p>Bring the full incident into view.</p>
        </div>
        <div className="fl-close-actions">
          <Link className="fl-close-entry" href="/login">
            <span>Open the operations centre</span>
            <ArrowUpRight size={46} weight="light" />
          </Link>
          <Link className="fl-secondary" href="/attack">
            Launch a live attack <ArrowRight size={18} />
          </Link>
        </div>
      </section>
      <footer className="fl-footer">
        <Link className="fl-brand" href="/">
          <LensMark />
          <span>FraudLens</span>
        </Link>
        <p>
          A working showcase with synthetic transactions and a separate bank simulator.
          <br />
          No external bank connection. Real-world detection performance is not claimed.
          <br />
          Demo data resets when the server restarts.
        </p>
        <a href="https://github.com/aahil62/fraud_lens" target="_blank" rel="noreferrer">
          <GithubLogo size={18} />
          View source <ArrowUpRight size={14} />
        </a>
      </footer>
    </div>
  );
}
