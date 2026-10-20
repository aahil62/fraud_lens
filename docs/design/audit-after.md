# Design audit: after the redesign (20 October 2026)

Same method as [audit-before.md](audit-before.md): the `unslop:audit` checklist with its `contrast-check` script, the `anti-slop` design law, and a scripted Playwright pass (`docs/screenshots/v4/`). Chosen direction: graphite + brass palette; Tanker for landing and attack headlines, Erode for titles, Mona Sans for body text, Courier Prime for IDs and amounts (user decisions, 20 October 2026).

## Score: 97 / 100 (28 of 29 applicable checks pass), up from 59

| Category | Before | After | What changed |
| --- | ---: | ---: | --- |
| Typography | 2 / 5 | 5 / 5 | 4 weights (400/500/600/700) instead of 23; a 10-step scale with a 12 px floor instead of 30 sizes; four faces with fixed roles |
| Spacing | 1 / 2 | 2 / 2 | Every padding and gap is a 4 px token; sections vary their rhythm (the peak has the most room) |
| Colour | 2 / 5 | 5 / 5 | No blue, indigo or purple; one accent (brass); 0 rendered contrast failures (landing was 2) |
| Surfaces | 2 / 3 | 3 / 3 | Three radii by role (4/8/14 px) instead of 15; tonal depth instead of white boxes on grey |
| Icons and imagery | 3 / 3 | 3 / 3 | Unchanged: Phosphor only |
| Motion | 4 / 4 | 4 / 4 | Parallax and the lens stop under reduced motion; buttons change colour, never move |
| States | 3 / 3 | 3 / 3 | No horizontal overflow at 390 or 1280 px on any of 14 pages |
| Layout | 0 / 4 | 3 / 4 | See L1 below |

S3 (touch targets) is again excluded: mobile menu, search, account and primary controls were raised to 44 px, but not every control was measured.

## Evidence

- **Tokens.** `frontend/app/tokens.css` is the only file with raw colours; `app/tokens.test.ts` fails on any hex, `0x` or `rgb()` colour in `app/`, `components/` or `lib/` (the vendored `scrollcraft.js` engine is excluded because it holds no palette). Outside the tokens, the stylesheets contain no raw `font-weight`, `font-size` or colour values. The only raw radii are 1–3 px rounded caps on thin bars and meters.
- **Contrast (computed WCAG ratios, every token text pair used):**

| Pair | Ratio |
| --- | ---: |
| Ink on surface / canvas | 15.77 / 13.89 |
| Muted on surface / canvas / sunken | 6.39 / 5.63 / 6.11 |
| Brass text on surface / canvas / brass tint | 6.07 / 5.34 / 5.34 |
| Brass-ink on brass button / hover | 6.84 / 8.00 |
| Bone on graphite / raised | 15.90 / 14.33 |
| Muted on graphite / raised / raised-2 / footer | 7.51 / 6.77 / 5.98 / 7.87 |
| Brass on graphite / raised-2 | 8.19 / 6.52 |
| Risk on surface / risk tint; strong risk on tint | 6.22 / 5.43; 7.16 |
| Risk on graphite / raised | 6.75 / 6.08 |
| Held on held tint / surface; held on graphite | 5.39 / 5.96; 7.88 |
| White on held / frozen / closed / risk chips | 6.44 / 6.87 / 17.04 / 6.72 |
| Caution on caution tint / surface | 5.26 / 5.77 |
| Bone on L2 chip; brass on supervisor chip | 9.88; 8.19 |
| Focus ring on surface / graphite | 6.07 / 8.19 |

  `contrast-check.mjs` on the rendered `/`, `/attack` and `/login`: all sampled pairs pass (landing 21 pairs, before: 2 failures).
- **Keyboard.** Tabbing through landing, attack and dashboard at 1280 and 390 px: every focused element shows a 2 px ring (brass-400 on graphite, brass-700 on stone; two topbar items at 390 px resolve to an ink ring, still 15:1). The mobile drawer takes focus on open, traps Tab, closes on Escape and returns focus to the menu button (`ConsoleShell.test.tsx` and a browser run).
- **Reduced motion.** With `prefers-reduced-motion: reduce` emulated, the landing renders the SVG lens (`.lens-poster` visible) and creates no WebGL canvas; with motion allowed, one canvas renders. Scrollcraft parallax returns `transform: none` under reduced motion; the golden-hour locks show statically.

## Resolved findings

| Before | After |
| --- | --- |
| C1 cobalt `#4058d5`, navy `#202a43`, blue-charcoal attack page | Warm graphite `#151513`, stone `#e9e8e3`, brass `#c39a4a`; no blue anywhere |
| C2 cobalt and red both acting as "primary" | Brass is the only action colour on every page, including the attack launch |
| T5 115 declarations at 8–10 px | None below 12 px |
| L3 four equal role cards; four boxed KPI tiles | Role section is an authority ladder (L1 → L2 → Supervisor, agent outside it, dashed); KPIs are one graphite ledger band |
| L4 flat cool grey with white boxes, hard navy band | Chapters alternate graphite and stone; grain and directional brass light on the opening; the peak (sample incident) is its own graphite chapter |
| Three products in one repo | One palette and type system across landing, console, auth and attack |
| Attack page without a brand mark | Lens mark and the same Erode wordmark as everywhere else |
| "Analyst workspace" box with a dropdown caret that did nothing | Same text, no caret |

## Remaining

- **L1 (partial).** The hero no longer reads as the stock left-column stack: the poster headline is the bottom plane crossing in front of the lens, and the lead sits top-left. But the copy is fixed, so a kicker line ("Financial crime. In focus.") and a button-plus-link pair remain.
- **Copy-level tells kept on purpose** (copy must not change in this stage): two em dashes in the golden-hour paragraph, the repeated agent-brief and "why flagged" reason lists on the case page, the "Inside an incident" and "The golden hour" kickers.
- **Fonts load from Fontshare's CDN** at runtime (declared in `app/fonts.css`); offline or blocked, Tanker and Erode fall back to Impact/Arial Narrow and Georgia. The first Stage B commit linked Fontshare's stylesheet with one combined request that returned only Tanker, so Erode was silently falling back to the system serif; the later fix declares each face directly.
- **Mobile Lighthouse performance is lower than before the redesign** (see `docs/VERIFICATION.md`, Stage B): the third-party font origin delays first paint by about 0.9 s on simulated 4G, and the 3D lens costs main-thread time on a throttled CPU. Serving Tanker and Erode from our own origin (fetched at Docker build time, not committed) would remove the first cost.
- Not checked: a real phone, a screen reader, browsers other than Chromium.
