import { RoleChip } from "../../operations/RoleChip";

/** Authority as a ladder: each role can do more than the one above it; the agent sits outside it. */
export function Team() {
  return (
    <section className="fl-team fl-section" id="team-authority" aria-labelledby="team-heading">
      <h2 id="team-heading">One team, clear authority.</h2>
      <div className="fl-team-grid">
        <div>
          <RoleChip role="l1_analyst" />
          <h3>L1 Analyst</h3>
          <p>Claims and investigates cases, escalates, and places liens on traced funds. Asks a senior analyst to approve anything bigger.</p>
        </div>
        <div>
          <RoleChip role="l2_analyst" />
          <h3>L2 Senior Analyst</h3>
          <p>Freezes debits, releases liens, confirms fraud or clears false alarms, assigns work and approves L1 requests.</p>
        </div>
        <div>
          <RoleChip role="supervisor" />
          <h3>Fraud Supervisor</h3>
          <p>Closes mule accounts after confirmed fraud, records the NCRP report, approves the final calls and sets agent policy.</p>
        </div>
        <div className="fl-team-agent">
          <span className="fl-agent-chip">Agent</span>
          <h3>FraudLens Agent</h3>
          <p>Triages, drafts, holds funds within policy. Never decides.</p>
        </div>
      </div>
    </section>
  );
}
