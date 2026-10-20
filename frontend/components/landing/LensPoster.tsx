/** The static lens: shown before WebGL is ready, without WebGL, and under reduced motion.
 * Colours come from the --lens-* tokens. */
const stop = (color: string, opacity = 1) => ({ stopColor: `var(${color})`, stopOpacity: opacity });

export function LensPoster() {
  return (
    <svg className="lens-poster" viewBox="0 0 1100 570" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="poster-metal" x1="560" y1="90" x2="860" y2="470" gradientUnits="userSpaceOnUse">
          <stop style={stop("--graphite-400")} />
          <stop offset=".35" style={stop("--graphite-700")} />
          <stop offset=".6" style={stop("--graphite-500")} />
          <stop offset="1" style={stop("--graphite-900")} />
        </linearGradient>
        <linearGradient id="poster-bezel" x1="560" y1="100" x2="840" y2="460" gradientUnits="userSpaceOnUse">
          <stop style={stop("--brass-200")} />
          <stop offset=".45" style={stop("--brass-500")} />
          <stop offset="1" style={stop("--brass-800")} />
        </linearGradient>
        <radialGradient id="poster-glass" cx="640" cy="220" r="220" gradientUnits="userSpaceOnUse">
          <stop style={stop("--graphite-500", 0.55)} />
          <stop offset=".6" style={stop("--graphite-850", 0.85)} />
          <stop offset="1" style={stop("--graphite-975", 0.95)} />
        </radialGradient>
      </defs>
      {[0, 1, 2, 3].map((lane) => (
        <path
          key={lane}
          className={lane === 0 ? "poster-path is-active" : "poster-path"}
          d={`M-50 ${240 + lane * 46} C230 ${240 + lane * 46} 440 ${385 + lane * 10} 676 290 S925 ${240 + lane * 46} 1150 ${210 + lane * 40}`}
          strokeWidth={lane === 0 ? 2.5 : 1.2}
        />
      ))}
      <g transform="rotate(-14 720 280)">
        <ellipse cx="741" cy="284" rx="142" ry="184" fill="url(#poster-metal)" />
        <ellipse cx="715" cy="280" rx="149" ry="188" fill="url(#poster-metal)" />
        <ellipse cx="700" cy="277" rx="149" ry="188" fill="url(#poster-bezel)" />
        <ellipse cx="700" cy="277" rx="135" ry="171" fill="url(#poster-glass)" />
        <ellipse className="poster-ring" cx="700" cy="277" rx="119" ry="150" strokeWidth="1" />
        <ellipse className="poster-ring" cx="700" cy="277" rx="91" ry="115" strokeWidth="1" />
        <ellipse className="poster-core" cx="700" cy="277" rx="45" ry="57" strokeWidth="1" />
        {Array.from({ length: 48 }, (_, i) => (
          <path
            key={i}
            className="poster-tick"
            d="M700 93v8"
            strokeWidth={i % 4 === 0 ? 2 : 1}
            transform={`rotate(${i * 7.5} 700 277)`}
          />
        ))}
        <path
          className="poster-glint"
          d="M634 140c-38 35-63 89-65 143"
          strokeWidth="6"
          strokeLinecap="round"
        />
      </g>
      <path className="poster-review" d="M712 292C855 293 815 110 1012 119" strokeWidth="2" />
      <circle className="poster-review-dot" cx="1012" cy="119" r="6" />
      <circle className="poster-signal-dot" cx="395" cy="292" r="5" />
    </svg>
  );
}
