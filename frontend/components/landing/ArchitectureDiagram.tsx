const BOXES = [
  { id: "in", x: 0, y: 20, w: 180, title: "Synthetic stream", sub: ["+ public Attack console"] },
  { id: "det", x: 250, y: 20, w: 210, title: "Detector", sub: ["rules · velocity · behaviour", "graph · reference ML"] },
  { id: "led", x: 510, y: 20, w: 200, title: "Case ledger + outbox", sub: ["SQLite, transactional"] },
  { id: "bank", x: 510, y: 160, w: 200, title: "Bank server", sub: ["separate service", "lien · freeze · close"] },
  { id: "ui", x: 250, y: 160, w: 210, title: "Live console", sub: ["multi-analyst", "roles + approvals"] },
];
const ARROWS = [
  { d: "M180 57 H246", label: "payments", lx: 213, ly: 47 },
  { d: "M460 57 H506", label: "cases", lx: 483, ly: 47 },
  { d: "M640 98 V156", label: "bank actions", lx: 676, ly: 131 },
  { d: "M510 205 H464", label: "acks", lx: 487, ly: 195 },
  { d: "M560 98 C 540 130, 470 140, 430 156", label: "live events", lx: 520, ly: 146 },
];
const STEPS = [
  ["Synthetic stream + Attack console", "payments"],
  ["Detector — rules · velocity · behaviour · graph · reference ML", "scored cases"],
  ["Case ledger + outbox — SQLite, transactional", "bank actions"],
  ["Bank server — separate service: lien · freeze · close", "acknowledgements + live events"],
  ["Live console — multi-analyst, roles + approvals", ""],
];
export default function ArchitectureDiagram() {
  return <figure className="fl-arch">
    <svg className="fl-arch-wide" viewBox="0 0 720 260" role="img" aria-labelledby="arch-title">
      <title id="arch-title">FraudLens architecture: synthetic stream and attack console feed the detector; cases go to a transactional ledger and outbox; bank actions go to a separate bank server; acknowledgements and live events reach the multi-analyst console.</title>
      <defs><marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#4058d5" /></marker></defs>
      {ARROWS.map((a) => <g key={a.label}><path d={a.d} fill="none" stroke="#4058d5" strokeWidth="1.6" markerEnd="url(#arch-arrow)" />
        <text x={a.lx} y={a.ly} textAnchor="middle" fontSize="11" fill="#626d80">{a.label}</text></g>)}
      {BOXES.map((b) => <g key={b.id}>
        <rect x={b.x} y={b.y} width={b.w} height="78" rx="12" fill="#fff" stroke="#dce2ed" />
        <text x={b.x + 16} y={b.y + 28} fontSize="15" fontWeight="650" fill="#202635">{b.title}</text>
        {b.sub.map((line, i) => <text key={line} x={b.x + 16} y={b.y + 48 + i * 16} fontSize="11.5" fill="#626d80">{line}</text>)}
      </g>)}
    </svg>
    <ol className="fl-arch-steps">{STEPS.map(([name, flow]) => <li key={name}><strong>{name}</strong>{flow && <span>↓ {flow}</span>}</li>)}</ol>
  </figure>;
}
