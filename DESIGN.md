# FraudLens design system

## Intent

A bank vault's control room. Warm graphite chrome and stone work surfaces, one brass accent, and retro type that reads like a printed bank ledger. The landing, the console and the attack page share one palette; their moods differ only by how much of the page sits on graphite. Decided with the user on 20 October 2026 from the mockups in `docs/design/palette-concepts.html` and `docs/design/type-concepts.html`.

## Tokens

`frontend/app/tokens.css` is the only file that holds raw colour values (`app/tokens.test.ts` fails on a hex, `0x` or `rgb()` colour anywhere else in `app/`, `components/` or `lib/`). It has three layers: primitives (named by what they are), semantic tokens (named by meaning) and component tokens.

| Role | Token | Value |
| --- | --- | --- |
| Chrome, landing opening, attack page | `--dark` | `#151513` |
| Raised dark surface | `--dark-raised` | `#201f1c` |
| Console canvas | `--canvas` | `#e9e8e3` |
| Reading surface | `--surface` | `#f7f6f3` |
| Ink / secondary text | `--ink` / `--muted` | `#1d1c19` / `#5c5a53` |
| Accent fill (one primary action per screen) | `--accent` | `#c39a4a` |
| Accent text on light / on dark | `--accent-text` / `--accent-on-dark` | `#7a5717` / `#d2a756` |
| Risk, fraud, declined | `--risk` | `#a3362e` |
| Frozen | `--frozen` | `#4d5d62` |
| Held, confirmed, posted | `--held` | `#2c6a47` |
| Closed | `--closed` | `#1d1c19` |
| Delivery problems | `--caution` | `#835812` |

Pending states (a request not yet acknowledged, an unresolved case) use a **dashed outline**, not a colour, so a request never looks like its confirmed effect. Status colours carry meaning only. Every text pair meets WCAG AA; the lowest is 5.26:1 (see `docs/design/audit-after.md`).

## Type

| Role | Face | Source |
| --- | --- | --- |
| Landing and attack headlines | Tanker (condensed poster capitals) | Fontshare, fetched at build time into the gitignored `public/fonts/` and served same-origin, CDN fallback (`app/fonts.css`; the ITF Free Font License forbids redistributing the files from this repository) |
| Page titles and section headings | Erode (1970s serif) | Same as Tanker |
| Body and controls | Mona Sans Variable | bundled `@fontsource-variable/mona-sans` (OFL) |
| IDs, amounts, scores, timestamps | Courier Prime (typewriter) | bundled `@fontsource/courier-prime` (OFL) |

Scale: 12, 13, 14, 16, 18, 22, 28, 36, 48, 64 px; 12 px is the floor for running text. Weights 400, 500, 600, 700. Each family has a system fallback.

## Shape and depth

Three radii by role: chips 4 px, controls 8 px, surfaces 14 px. Depth comes from tone (graphite against stone, paper against stone), not shadows; overlays use one tight directional shadow. The one bespoke silhouette is a clipped top-right corner, used on the landing dossier, the agent brief and the selected scam.

## Layout and interactions

- Console: 232 px graphite rail with a brass inset bar on the current item; paper top bar; stone canvas; the dashboard's figures sit in one graphite ledger band.
- Mobile: the rail becomes a focus-contained drawer, the main content is inert while it is open, Escape closes it and focus returns to the trigger.
- Tables keep full records in a horizontal scroll region; no viewport-wide overflow at 390 px.
- Search is a native dialog with keyboard and Escape support.
- Buttons change colour on hover and never move.

## Landing

Chapters alternate graphite and stone: the opening, the sample incident (the page's peak) and the ending sit on graphite. The hero is three planes: brass light from the upper right with fine grain, the Three.js lens (blackened steel, brass bezel, smoky glass, studio reflections, colours read from the `--lens-*` tokens), and the Tanker headline crossing in front of it, with slight opposing parallax from the unchanged Scrollcraft engine. A complete SVG lens (`LensPoster.tsx`) shows when WebGL is absent or software-rendered (no GPU), the visitor pauses 3D, or reduced motion is requested. Offscreen and hidden-page rendering stops; GPU resources are disposed on cleanup. Content is visible by default.

## Evidence and maintenance

Use semantic controls, visible focus, AA contrast, clear error/loading/empty states and reduced-motion alternatives. A screenshot or green unit test alone does not certify accessibility or performance. Keep example data and operational metrics clearly separate; never add fake customers, savings, trends, accuracy or compliance badges.
