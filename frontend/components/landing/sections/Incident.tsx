import { ArrowRight, Check, CheckCircle, Fingerprint, GitBranch, ShieldCheck } from "@phosphor-icons/react";
import { channels, type ChannelKey } from "../channels";

const stageNames = ["The signal", "The protection", "The decision"];
type Channel = (typeof channels)[number];

function SignalStage({ channel, onNext }: { channel: Channel; onNext: () => void }) {
  return (
    <>
      <div className="fl-stage-title">
        <GitBranch size={21} />
        <h4>Context turns an alert into a case.</h4>
      </div>
      <p>Read the pattern around this payment. Each observation gives the analyst a reason to investigate.</p>
      <ol className="fl-evidence-list">
        {channel.signals.map((signal, index) => (
          <li key={signal}>
            <span className="fl-evidence-index">0{index + 1}</span>
            <span>{signal}</span>
            <CheckCircle size={18} />
          </li>
        ))}
      </ol>
      <button type="button" className="fl-stage-action" onClick={onNext}>
        Inspect the protection state <ArrowRight size={18} />
      </button>
    </>
  );
}

function ProtectionStage({ channel, onNext }: { channel: Channel; onNext: () => void }) {
  const request =
    channel.key === "card" || channel.key === "atm" ? "Instrument restriction" : "Account debit restriction";
  return (
    <>
      <div className="fl-stage-title">
        <ShieldCheck size={21} />
        <h4>A request isn’t an acknowledgement.</h4>
      </div>
      <p>
        The bank simulator returns its own state. The workspace keeps the request, response and protected
        scope together.
      </p>
      <dl className="fl-protection-state">
        <div>
          <dt>Protection request</dt>
          <dd>{request}</dd>
        </div>
        <div>
          <dt>Bank simulator</dt>
          <dd>
            <CheckCircle size={16} weight="fill" /> Acknowledged
          </dd>
        </div>
        <div>
          <dt>Protected scope</dt>
          <dd>{channel.scope}</dd>
        </div>
      </dl>
      <button type="button" className="fl-stage-action" onClick={onNext}>
        Move to the analyst decision <ArrowRight size={18} />
      </button>
    </>
  );
}

function DecisionStage({
  channel,
  resolved,
  onRecord,
  onReplay,
}: {
  channel: Channel;
  resolved: boolean;
  onRecord: () => void;
  onReplay: () => void;
}) {
  return (
    <>
      <div className="fl-stage-title">
        <Fingerprint size={21} />
        <h4>{resolved ? "The reasoning stays with the record." : "The final call belongs to an analyst."}</h4>
      </div>
      <p>
        {resolved
          ? "The sample verdict is now connected to its observations and simulated protection state. Every part of the incident tells the same story."
          : "In this example, the observations support a suspicious verdict. Record it to complete the sample investigation."}
      </p>
      <div className={`fl-verdict${resolved ? " fl-verdict--recorded" : ""}`}>
        <span>{resolved ? <CheckCircle size={26} weight="fill" /> : <Fingerprint size={26} />}</span>
        <div>
          <span>{resolved ? "Sample verdict recorded" : "Proposed sample verdict"}</span>
          <strong>{channel.verdict}</strong>
        </div>
      </div>
      {resolved ? (
        <button type="button" className="fl-stage-action" onClick={onReplay}>
          Replay this example <ArrowRight size={18} />
        </button>
      ) : (
        <button type="button" className="fl-stage-action" onClick={onRecord}>
          Record sample verdict <Check size={18} weight="bold" />
        </button>
      )}
    </>
  );
}

/** The page's peak: an interactive, clearly labelled sample investigation. */
export function Incident({
  channelKey,
  stage,
  resolved,
  onStage,
  onResolved,
}: {
  channelKey: ChannelKey;
  stage: number;
  resolved: boolean;
  onStage: (stage: number) => void;
  onResolved: (resolved: boolean) => void;
}) {
  const channel = channels.find((item) => item.key === channelKey)!;
  return (
    <section
      className="fl-incident-section"
      id="sample-incident"
      data-sc-act="flow"
      aria-labelledby="incident-heading"
    >
      <div className="fl-incident-intro">
        <p className="fl-section-note">Inside an incident</p>
        <h2 id="incident-heading">
          The alert is just
          <br />
          <span>the beginning.</span>
        </h2>
        <p>
          A score asks for attention. Evidence, an acknowledged protection state and a recorded verdict make
          the work traceable.
        </p>
        <div className="fl-demo-label">
          <span />
          Interactive example · synthetic data
        </div>
      </div>
      <div className="fl-incident-dossier">
        <div className="fl-dossier-heading">
          <div>
            <span className="fl-dossier-label">Sample investigation</span>
            <h3>{channel.scenario}</h3>
          </div>
          <span className="fl-rail-name">{channel.name}</span>
        </div>
        <div className="fl-transaction">
          <div>
            <span>Flagged payment</span>
            <strong>{channel.amount}</strong>
          </div>
          <div>
            <span>{channel.account}</span>
            <p>{channel.event}</p>
          </div>
          <span className={resolved ? "fl-sample-status fl-sample-status--done" : "fl-sample-status"}>
            {resolved ? "Reviewed" : "For review"}
          </span>
        </div>
        <div className="fl-incident-steps" role="group" aria-label="Sample investigation stages">
          {stageNames.map((name, index) => (
            <button
              key={name}
              type="button"
              className={stage === index ? "is-current" : ""}
              aria-pressed={stage === index}
              onClick={() => onStage(index)}
            >
              <span>{index < stage || resolved ? <Check size={13} weight="bold" /> : index + 1}</span>
              {name}
            </button>
          ))}
        </div>
        <div className="fl-stage-content" aria-live="polite" aria-atomic="true">
          {stage === 0 && <SignalStage channel={channel} onNext={() => onStage(1)} />}
          {stage === 1 && <ProtectionStage channel={channel} onNext={() => onStage(2)} />}
          {stage === 2 && (
            <DecisionStage
              channel={channel}
              resolved={resolved}
              onRecord={() => onResolved(true)}
              onReplay={() => {
                onResolved(false);
                onStage(0);
              }}
            />
          )}
        </div>
        <div className="fl-dossier-footer">
          <span className="fl-dossier-dot" />
          <span>
            {resolved
              ? "Example complete. Evidence, protection and verdict connected."
              : "Follow each stage to close the example."}
          </span>
          <span>{stage + 1} / 3</span>
        </div>
      </div>
      <div className="fl-incident-takeaway">
        <span>Clear signals.</span>
        <span>Traceable actions.</span>
        <span>Accountable decisions.</span>
      </div>
    </section>
  );
}
