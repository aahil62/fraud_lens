const NODES = [
  { x: 40, label: "Victim" },
  { x: 180, label: "Mule 1", lock: true },
  { x: 320, label: "Mule 2", lock: true },
  { x: 460, label: "ATM" },
];
function Lock({ x, delay }: { x: number; delay: string }) {
  // The outer group positions; the inner group animates (CSS transforms replace SVG transform attributes).
  return (
    <g transform={`translate(${x - 9} 22)`} aria-hidden="true">
      <g className="fl-gh-lock" style={{ animationDelay: delay }}>
        <rect className="gh-lock-body" x="1" y="8" width="16" height="12" rx="3" />
        <path className="gh-lock-shackle" d="M5 8V5.5a4 4 0 0 1 8 0V8" fill="none" strokeWidth="2" />
      </g>
    </g>
  );
}
export default function GoldenHour({ paused = false }: { paused?: boolean }) {
  return (
    <section
      className={`fl-golden fl-section${paused ? " is-paused" : ""}`}
      id="golden-hour"
      aria-labelledby="golden-heading"
    >
      <div className="fl-golden-copy">
        <p className="fl-section-kicker">The golden hour</p>
        <h2 id="golden-heading">When a victim calls 1930, the clock starts.</h2>
        <p>
          Money moves through mule accounts in minutes. FraudLens traces every hop and places holds on
          what&apos;s left — automatically — then hands the case to the right analyst.
        </p>
      </div>
      <figure className="fl-golden-figure">
        <svg viewBox="0 0 500 130" role="img" aria-labelledby="golden-svg-title">
          <title id="golden-svg-title">
            A payment travels from the victim through two mule accounts to an ATM; holds appear on both mule
            accounts.
          </title>
          <line className="gh-track" x1="40" y1="70" x2="460" y2="70" strokeWidth="2" strokeDasharray="4 6" />
          <circle className="fl-gh-coin" cx="40" cy="70" r="7" />
          {NODES.map((node) => (
            <g key={node.label}>
              <circle
                className={node.lock ? "gh-node is-mule" : "gh-node"}
                cx={node.x}
                cy="70"
                r="16"
                strokeWidth="2"
              />
              <text className="gh-label" x={node.x} y="114" textAnchor="middle" fontSize="16">
                {node.label}
              </text>
            </g>
          ))}
          <Lock x={180} delay="1.4s" />
          <Lock x={320} delay="2.6s" />
        </svg>
        <figcaption>Illustrative example · fictional accounts</figcaption>
      </figure>
    </section>
  );
}
