"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight } from "@phosphor-icons/react";
import { type Guidance, type Snapshot, channelName, human, opsFetch } from "@/lib/operations";
import { useOperations } from "../OperationsProvider";
import { Loading, PageHeading } from "../Primitives";

function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.join(" · ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function DetectionCoverage({ snapshot }: { snapshot: Snapshot | null }) {
  return (
    <section className="ops-section">
      <div className="section-heading">
        <div>
          <h2>Detection coverage</h2>
          <p>
            Version {snapshot?.detection.version ?? "…"}. Transparent scenario coverage is not real-world
            accuracy.
          </p>
        </div>
      </div>
      <div className="coverage-list coverage-disclosures">
        {snapshot?.detection.coverage.map((row, i) => (
          <details key={i}>
            <summary>
              <span>
                {typeof row.channel === "string" ? channelName(row.channel) : `Detection coverage ${i + 1}`}
              </span>
              <span>View supported signals</span>
            </summary>
            <div>
              {Object.entries(row).map(([key, value]) => (
                <p key={key}>
                  <strong>{human(key)}: </strong>
                  {formatValue(value)}
                </p>
              ))}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

function Requirements({ requirements }: { requirements: NonNullable<Guidance["requirements"]> }) {
  const issuers = [...new Set(requirements.map((row) => row.issuer))];
  return (
    <section className="ops-section">
      <div className="section-heading">
        <div>
          <h2>1930 / NCRP, RBI and NPCI requirements</h2>
          <p>Grouped by issuer. Paraphrased; unverified items are labelled.</p>
        </div>
      </div>
      {issuers.map((issuer) => (
        <div key={issuer} className="guidance-issuer">
          <h3>{issuer}</h3>
          <div className="guidance-list">
            {requirements
              .filter((row) => row.issuer === issuer)
              .map((row) => (
                <details key={row.source} className="guidance-disclosure">
                  <summary>
                    <span>
                      <strong>{row.source}</strong>
                      <small>
                        {row.date} · {row.status}
                      </small>
                    </span>
                    <span>Read mapping</span>
                  </summary>
                  <div className="guidance-detail">
                    {row.url ? (
                      <a href={row.url} target="_blank" rel="noreferrer" className="guidance-source">
                        Open source <ArrowUpRight size={15} />
                      </a>
                    ) : (
                      <p className="fine-print">No primary source verified.</p>
                    )}
                    <dl>
                      <dt>What it requires</dt>
                      <dd>{row.what_it_requires}</dd>
                      <dt>How FraudLens models it</dt>
                      <dd>{row.how_fraudlens_models_it}</dd>
                      <dt>Not covered</dt>
                      <dd>{row.not_covered}</dd>
                    </dl>
                  </div>
                </details>
              ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function EvidenceMatrix({ guidance, error }: { guidance: Guidance | null; error: string }) {
  return (
    <section className="ops-section">
      <div className="section-heading">
        <h2>Requirements-to-evidence matrix</h2>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {guidance ? (
        <div className="guidance-list">
          {guidance.references.map((row) => (
            <details key={row.id} className="guidance-disclosure">
              <summary>
                <span>
                  <strong>{row.title}</strong>
                  <small>
                    {row.source_date} · {row.status}
                  </small>
                </span>
                <span>Read control & evidence</span>
              </summary>
              <div className="guidance-detail">
                <a href={row.source_url} target="_blank" rel="noreferrer" className="guidance-source">
                  Open source reference <ArrowUpRight size={15} />
                </a>
                <dl>
                  <dt>Applicability</dt>
                  <dd>{row.applicability}</dd>
                  <dt>Control</dt>
                  <dd>{row.control}</dd>
                  <dt>Evidence</dt>
                  <dd>{row.test_evidence.join("; ") || "Not yet verified"}</dd>
                </dl>
              </div>
            </details>
          ))}
        </div>
      ) : (
        !error && <Loading />
      )}
    </section>
  );
}

export function GuidanceView() {
  const { snapshot } = useOperations();
  const [guidance, setGuidance] = useState<Guidance | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void opsFetch<Guidance>("/guidance")
      .then((data) => {
        if (active) setGuidance(data);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Guidance unavailable.");
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <PageHeading
        title="Controls & guidance"
        description="Source-linked applicability and implemented controls. Alignment requires evidence, not a badge."
      />
      <section className="boundary-note">
        <strong>Scope and limitations</strong>
        <p>
          {guidance?.disclaimer ??
            "Local synthetic showcase. Formal NPCI approval, regulatory certification and real-bank validation are not claimed."}
        </p>
      </section>
      <DetectionCoverage snapshot={snapshot} />
      {guidance?.requirements && <Requirements requirements={guidance.requirements} />}
      <EvidenceMatrix guidance={guidance} error={error} />
    </>
  );
}
