"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowRight, ArrowUpRight, Bank, Check, CheckCircle, CreditCard, Fingerprint, GitBranch, GithubLogo, MagnifyingGlass, ShieldCheck } from "@phosphor-icons/react";
import LensScene from "./LensScene";
import { channels, type ChannelKey } from "./channels";

type ScrollCraftWindow = Window & { ScrollCraft?: { mount: (root: HTMLElement) => { destroy: () => void } } };
const stageNames = ["The signal", "The protection", "The decision"];
const channelIcons = [Fingerprint, Bank, CreditCard, Bank];

function BrandMark() {
  return <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true"><circle cx="12" cy="15" r="9" stroke="currentColor" strokeWidth="2.3" /><path d="M18 6a9 9 0 1 1 0 18" stroke="currentColor" strokeWidth="2.3" /><path d="M9 15h12" stroke="currentColor" strokeWidth="1.5" /></svg>;
}

export default function LandingExperience() {
  const rootRef = useRef<HTMLElement>(null);
  const [channelKey, setChannelKey] = useState<ChannelKey>("upi");
  const [stage, setStage] = useState(0);
  const [motionPaused, setMotionPaused] = useState(false);
  const [resolved, setResolved] = useState(false);
  const channel = channels.find((item) => item.key === channelKey)!;

  useEffect(() => {
    let canceled = false;
    let instance: { destroy: () => void } | undefined;
    async function mount() {
      // The skill engine stays unchanged. Only decorative depth uses scroll
      // progress; essential text and controls have no entrance attributes.
      await import("./scrollcraft.js");
      if (!canceled && rootRef.current) instance = (window as ScrollCraftWindow).ScrollCraft?.mount(rootRef.current);
    }
    void mount();
    return () => { canceled = true; instance?.destroy(); };
  }, []);

  function selectChannel(key: ChannelKey) {
    setChannelKey(key);
    setStage(0);
    setResolved(false);
  }

  function tabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") next = (index + 1) % channels.length;
    else if (event.key === "ArrowUp" || event.key === "ArrowLeft") next = (index + channels.length - 1) % channels.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = channels.length - 1;
    else return;
    event.preventDefault();
    selectChannel(channels[next].key);
    document.getElementById(`rail-tab-${channels[next].key}`)?.focus();
  }

  return (
    <main ref={rootRef} className="fl-landing">
      <a className="fl-skip" href="#sample-incident">Skip to the sample investigation</a>
      <header className="fl-nav">
        <Link className="fl-brand" href="/" aria-label="FraudLens home"><BrandMark /><span>FraudLens</span></Link>
        <nav aria-label="Main navigation"><a href="#payment-rails">The channels</a><a href="#sample-incident">Inside an incident</a></nav>
        <Link className="fl-nav-entry" href="/login">Open workspace <ArrowUpRight size={16} weight="bold" /></Link>
      </header>

      <section className="fl-hero" data-sc-act="flow" aria-labelledby="hero-heading">
        <div className="fl-hero-copy">
          <p className="fl-intro">Financial crime. In focus.</p>
          <h1 id="hero-heading">Follow the <span>signal.</span></h1>
        </div>
        <div className="fl-hero-imprint" aria-hidden="true" data-sc-parallax="-0.045">A clearer picture.</div>
        <LensScene key={motionPaused ? "static" : "animated"} channel={channelKey} animated={!motionPaused} />
        <div className="fl-hero-note">
          <p>From a suspicious payment<br />to a decision you can explain.</p>
          <Link className="fl-primary" href="/login">Open workspace <ArrowUpRight size={20} /></Link>
        </div>
        <div className="fl-lens-annotation"><span className="fl-annotation-line" /><span>Four payment rails.<br /><strong>One connected investigation.</strong></span></div>
        <div className="fl-hero-baseline"><span>Detection → Protection → Investigation</span><button className="fl-motion-control" type="button" aria-pressed={motionPaused} onClick={()=>setMotionPaused(!motionPaused)}>{motionPaused ? "Resume 3D motion" : "Pause 3D motion"}</button><span>Synthetic-data showcase</span></div>
      </section>

      <section className="fl-rails fl-section" id="payment-rails" data-sc-act="flow" aria-labelledby="rails-heading">
        <div className="fl-rails-heading"><h2 id="rails-heading">Different rails.<br /><span>One line of sight.</span></h2><p>Context changes from channel to channel.<br />The need for a clear decision doesn’t.</p><a className="fl-text-link" href="#sample-incident">Trace an example <ArrowRight size={18} /></a></div>
        <div className="fl-channel-surface">
          <div className="fl-channel-tabs" role="tablist" aria-label="Payment channel" aria-orientation="vertical">
            {channels.map((item, index) => {
              const Icon = channelIcons[index];
              return <button type="button" role="tab" key={item.key} id={`rail-tab-${item.key}`} aria-controls={`rail-panel-${item.key}`} aria-selected={channelKey === item.key} tabIndex={channelKey === item.key ? 0 : -1} onKeyDown={(event) => tabKey(event, index)} onClick={() => selectChannel(item.key)}><Icon size={22} weight={channelKey === item.key ? "fill" : "regular"} /><span>{item.name}</span><ArrowUpRight size={17} /></button>;
            })}
          </div>
          <div className="fl-channel-story" role="tabpanel" id={`rail-panel-${channelKey}`} aria-labelledby={`rail-tab-${channelKey}`} tabIndex={0}>
            <div className="fl-channel-trace" aria-hidden="true"><span /><span /><span /><span /><span /><i><MagnifyingGlass size={21} /></i><span /><span /></div>
            <h3>{channel.detail}</h3><p>{channel.description}</p>
            <span className="fl-channel-caption">Explore {channel.name} in the sample below <ArrowRight size={14} /></span>
          </div>
        </div>
      </section>

      <section className="fl-incident-section" id="sample-incident" data-sc-act="flow" aria-labelledby="incident-heading">
        <div className="fl-incident-intro"><p className="fl-section-note">Inside an incident</p><h2 id="incident-heading">The alert is just<br /><span>the beginning.</span></h2><p>A score asks for attention. Evidence, an acknowledged protection state and a recorded verdict make the work traceable.</p><div className="fl-demo-label"><span />Interactive example · synthetic data</div></div>
        <div className="fl-incident-dossier">
          <div className="fl-dossier-heading"><div><span className="fl-dossier-label">Sample investigation</span><h3>{channel.scenario}</h3></div><span className="fl-rail-name">{channel.name}</span></div>
          <div className="fl-transaction"><div><span>Flagged payment</span><strong>{channel.amount}</strong></div><div><span>{channel.account}</span><p>{channel.event}</p></div><span className={resolved ? "fl-sample-status fl-sample-status--done" : "fl-sample-status"}>{resolved ? "Reviewed" : "For review"}</span></div>
          <div className="fl-incident-steps" role="group" aria-label="Sample investigation stages">
            {stageNames.map((name, index) => <button key={name} type="button" className={stage === index ? "is-current" : ""} aria-pressed={stage === index} onClick={() => setStage(index)}><span>{index < stage || resolved ? <Check size={13} weight="bold" /> : index + 1}</span>{name}</button>)}
          </div>
          <div className="fl-stage-content" aria-live="polite" aria-atomic="true">
            {stage === 0 && <>
              <div className="fl-stage-title"><GitBranch size={21} /><h4>Context turns an alert into a case.</h4></div>
              <p>Read the pattern around this payment. Each observation gives the analyst a reason to investigate.</p>
              <ol className="fl-evidence-list">{channel.signals.map((signal, index) => <li key={signal}><span className="fl-evidence-index">0{index + 1}</span><span>{signal}</span><CheckCircle size={18} /></li>)}</ol>
              <button type="button" className="fl-stage-action" onClick={() => setStage(1)}>Inspect the protection state <ArrowRight size={18} /></button>
            </>}
            {stage === 1 && <>
              <div className="fl-stage-title"><ShieldCheck size={21} /><h4>A request isn’t an acknowledgement.</h4></div>
              <p>The bank simulator returns its own state. The workspace keeps the request, response and protected scope together.</p>
              <dl className="fl-protection-state"><div><dt>Protection request</dt><dd>{channel.key === "card" || channel.key === "atm" ? "Instrument restriction" : "Account debit restriction"}</dd></div><div><dt>Bank simulator</dt><dd><CheckCircle size={16} weight="fill" /> Acknowledged</dd></div><div><dt>Protected scope</dt><dd>{channel.scope}</dd></div></dl>
              <button type="button" className="fl-stage-action" onClick={() => setStage(2)}>Move to the analyst decision <ArrowRight size={18} /></button>
            </>}
            {stage === 2 && <>
              <div className="fl-stage-title"><Fingerprint size={21} /><h4>{resolved ? "The reasoning stays with the record." : "The final call belongs to an analyst."}</h4></div>
              <p>{resolved ? "The sample verdict is now connected to its observations and simulated protection state. Every part of the incident tells the same story." : "In this example, the observations support a suspicious verdict. Record it to complete the sample investigation."}</p>
              <div className={`fl-verdict${resolved ? " fl-verdict--recorded" : ""}`}><span>{resolved ? <CheckCircle size={26} weight="fill" /> : <Fingerprint size={26} />}</span><div><span>{resolved ? "Sample verdict recorded" : "Proposed sample verdict"}</span><strong>{channel.verdict}</strong></div></div>
              {resolved ? <button type="button" className="fl-stage-action" onClick={() => { setResolved(false); setStage(0); }}>Replay this example <ArrowRight size={18} /></button> : <button type="button" className="fl-stage-action" onClick={() => setResolved(true)}>Record sample verdict <Check size={18} weight="bold" /></button>}
            </>}
          </div>
          <div className="fl-dossier-footer"><span className="fl-dossier-dot" /><span>{resolved ? "Example complete. Evidence, protection and verdict connected." : "Follow each stage to close the example."}</span><span>{stage + 1} / 3</span></div>
        </div>
        <div className="fl-incident-takeaway"><span>Clear signals.</span><span>Traceable actions.</span><span>Accountable decisions.</span></div>
      </section>

      <section className="fl-close fl-section" data-sc-act="flow" aria-labelledby="close-heading">
        <div className="fl-close-statement"><BrandMark /><h2 id="close-heading">Less guesswork.<br /><span>More clarity.</span></h2><p>Bring the full incident into view.</p></div>
        <Link className="fl-close-entry" href="/login"><span>Open workspace</span><ArrowUpRight size={46} weight="light" /></Link>
      </section>
      <footer className="fl-footer"><Link className="fl-brand" href="/"><BrandMark /><span>FraudLens</span></Link><p>A working showcase with synthetic transactions and a separate bank simulator.<br />No external bank connection. Real-world detection performance is not claimed.</p><a href="https://github.com/aahil62/fraud_lens" target="_blank" rel="noreferrer"><GithubLogo size={18} />View source <ArrowUpRight size={14} /></a></footer>
    </main>
  );
}
