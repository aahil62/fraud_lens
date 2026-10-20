import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "@phosphor-icons/react";
import { LensMark } from "../../console/LensMark";
import LensScene from "../LensScene";
import type { ChannelKey } from "../channels";

export function LandingNav() {
  return (
    <header className="fl-nav">
      <Link className="fl-brand" href="/" aria-label="FraudLens home">
        <LensMark />
        <span>FraudLens</span>
      </Link>
      <nav aria-label="Main navigation">
        <a href="#golden-hour">The golden hour</a>
        <a href="#payment-rails">The channels</a>
        <a href="#how-its-built">How it&apos;s built</a>
      </nav>
      <Link className="fl-nav-entry" href="/login">
        Open workspace <ArrowUpRight size={16} weight="bold" />
      </Link>
    </header>
  );
}

/** Three planes: the brass-lit backdrop, the lens, and the poster headline crossing in front of it. */
export function Hero({
  channel,
  motionPaused,
  onToggleMotion,
}: {
  channel: ChannelKey;
  motionPaused: boolean;
  onToggleMotion: () => void;
}) {
  return (
    <section className="fl-hero" data-sc-act="flow" aria-labelledby="hero-heading">
      <div className="fl-hero-copy" data-sc-parallax="-0.08">
        <p className="fl-intro">Financial crime. In focus.</p>
        <h1 id="hero-heading">
          Follow the <span>signal.</span>
        </h1>
      </div>
      <div className="fl-hero-lens" data-sc-parallax="0.06">
        <LensScene key={motionPaused ? "static" : "animated"} channel={channel} animated={!motionPaused} />
      </div>
      <div className="fl-hero-note">
        <p>
          From a suspicious payment <br />
          to a decision you can explain.
        </p>
        <div className="fl-cta-row">
          <Link className="fl-primary" href="/login">
            Open the operations centre <ArrowUpRight size={20} />
          </Link>
          <Link className="fl-secondary" href="/attack">
            Launch a live attack <ArrowRight size={18} />
          </Link>
        </div>
      </div>
      <div className="fl-lens-annotation">
        <span className="fl-annotation-line" />
        <span>
          Four payment rails.
          <br />
          <strong>One connected investigation.</strong>
        </span>
      </div>
      <div className="fl-hero-baseline">
        <span>Detection → Protection → Investigation</span>
        <button
          className="fl-motion-control"
          type="button"
          aria-pressed={motionPaused}
          onClick={onToggleMotion}
        >
          {motionPaused ? "Resume 3D motion" : "Pause 3D motion"}
        </button>
        <span>Synthetic-data showcase</span>
      </div>
    </section>
  );
}
