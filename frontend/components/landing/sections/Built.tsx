import ArchitectureDiagram from "../ArchitectureDiagram";
import { PROOF } from "../proof";

export function Built() {
  return (
    <section className="fl-built fl-section" id="how-its-built" aria-labelledby="built-heading">
      <h2 id="built-heading">How it&apos;s built</h2>
      <ArchitectureDiagram />
      <dl className="fl-proof">
        <div><dt>Payment channels</dt><dd>{PROOF.channels}</dd></div>
        <div><dt>Scam typologies you can launch</dt><dd>{PROOF.typologies}</dd></div>
        <div>
          <dt>Precision / recall at automatic protection (score ≥ {PROOF.protectionThreshold})</dt>
          <dd>{PROOF.precision.toFixed(4)} / {PROOF.recall.toFixed(4)}</dd>
        </div>
        <div><dt>Backend tests</dt><dd>{PROOF.backendTests}</dd></div>
      </dl>
      <p className="fl-proof-note">
        Precision and recall come from a constructed corpus of {PROOF.evaluationSamples} synthetic payments, not real bank data.{" "}
        <a href="https://github.com/aahil62/fraud_lens/blob/main/docs/OPERATIONS_EVALUATION.md" target="_blank" rel="noreferrer">Read the evaluation</a>.
      </p>
    </section>
  );
}
