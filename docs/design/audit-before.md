# Design audit: before the redesign (20 October 2026)

Branch `feature/fraudlens-v3` at `70a9877` (after Stage A). Audited with `unslop:audit` (checklist, `slop-scan`, `contrast-check`, overflow capture) and the `anti-slop` design law. Pages: landing `/`, dashboard, case page (`CASE-0D4E573825B3`, signed in as R. Iyer, L2) and `/attack`. Source is read-only for this audit.

Screenshots: [landing](before/landing/) and [attack](before/attack/) at 375/768/1024/1440 px; [dashboard and case](before/console/) at 390 and 1280 px.

## Score: 59 / 100 (17 of 29 applicable checks pass)

| Category | Pass / applicable | Notes |
| --- | ---: | --- |
| Typography | 2 / 5 | No locked weights or type scale |
| Spacing | 1 / 2 | S3 (touch targets) not measured, excluded |
| Colour | 2 / 5 | Accent in the rejected blue family; contrast failures |
| Surfaces | 2 / 3 | 15 radii, no roles |
| Icons and imagery | 3 / 3 | Phosphor only, no emoji, no stock imagery |
| Motion | 4 / 4 | Reduced-motion rules exist on every stylesheet |
| States | 3 / 3 | No overflow at any width; labelled forms |
| Layout | 0 / 4 | Template hero, same section skeleton, flat surfaces |

`slop-scan` found no Tailwind-class tells, because almost all styling is hand-written CSS. The failures below come from that CSS and from the rendered pages.

## Failures with evidence

### Typography
- **T1, too many weights.** 23 distinct `font-weight` values across the four stylesheets: 400, 450, 500, 520, 550, 560, 570, 580, 600, 620, 640, 650, 660, 680, 690, 700, 740, 760 and more (`grep -ohE "font-weight: ?[0-9]+" app/*.css app/attack/*.css`). Most are 10–20 units apart and cannot be told apart on screen.
- **T2, no type pairing.** Mona Sans carries display, body, labels and buttons on every page; the only other face is the system monospace (`globals.css` `--font-mono`). The landing headline "Follow the signal." has no typographic character distinct from the console's labels.
- **T5, no type scale.** 30 distinct sizes: every pixel from 8 px to 32 px, then 35, 36, 39, 44 and 63 px. 115 declarations set text at 8–10 px (`globals.css` 58, `landing.css` 32, `workspace-views.css` 25), e.g. `.graph-node-detail span` 9 px (`globals.css:373`), `.record-link` 10 px (`globals.css:165`). On the 1280 px case page, timeline references and the agent signal captions are hard to read.

### Spacing
- **S1, off-scale spacing.** Padding and gaps use arbitrary values rather than a 4 px scale: `.ops-sidebar { padding: 30px 16px 18px }` (`globals.css:94`), `.sidebar-sim { padding: 15px 12px }` (`:114`), `.fl-incident-steps button { padding: 21px 0 17px }` (`landing.css:98`), `.fl-incident-section { padding: 84px 5% 38px }` (`landing.css:77`).

### Colour
- **C1, rejected colour family.** The primary action, selection, links, chart bars and landing accent are cobalt `#4058d5` (`landing.css:5`, `:17`, `:100–102`; `globals.css` primary button). The landing's incident band is a dark navy `#202a43` (`landing.css:77`). The attack page is a cool blue-charcoal `#171b24` / `#202634` with a periwinkle `#8fa2ff` (`attack/attack.css:3`): the "cool blue-charcoal" dark default. The user ruled out blue, indigo and dark-blue themes.
- **C2, competing accents.** One screen mixes cobalt (buttons, bars), red (risk scores `95.0`, the lens's red path), amber (`For review` chip), green (`System live`) and grey-blue tints. The attack page switches the primary action to red (`#c23f45`) while the console uses cobalt, so the two halves of the product have different "primary" colours.
- **C3, contrast.** `contrast-check` on `/`: two WCAG AA failures, 9 px text on `rgb(251,239,219)` and 10 px `rgb(113,129,159)` on white (3.93:1). Visually, the disabled "Confirm fraud" and "Mark false positive & release" buttons on the case page (1280 px) are faint pink and pale blue with low-contrast labels.

### Surfaces
- **R1, no radius roles.** 15 radii in use: 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16 and 999 px. DESIGN.md says surfaces 16, controls 9 and labels 5, but the CSS does not follow it.

### Layout (anti-slop law)
- **L1, the template hero.** 1440 px landing: small kicker ("Financial crime. In focus.") → two-tone headline with one saturated cobalt word ("signal.") → two-line subline → filled button plus text link ("Open the operations centre" / "Launch a live attack") with the 3D lens panel on the right. That is the "hero stack with a panel on the right", the "two-tone accent headline" and the "filled button next to a text link" patterns together. The kicker-over-heading section opener repeats ("THE GOLDEN HOUR" above "When a victim calls 1930…").
- **L2, one section skeleton.** Golden hour, channels and incident all use left text column + right panel at the same container width; the closing "Less guesswork. More clarity." is a two-tone headline with a CTA on the right, the pre-footer CTA pattern.
- **L3, identical card grid.** "One team, clear authority." is four equal cards (L1, L2, Supervisor, Agent) with tinted role chips; only the Agent card is tinted. The dashboard's four KPI tiles (Payment attempts, Awaiting review, Resolved, Active restrictions) are identical boxed number tiles with icons top-right.
- **L4, flat surfaces.** The landing sits on a flat cool grey (`#f5f7fb`, the UI-kit neutral) with white boxes; the only depth is the navy band, which cuts in and out with hard seams top and bottom (1440 px, between "Different rails" and "One team").

### Page-specific findings
- **No shared visual world.** Landing (light cool grey and cobalt), console (charcoal rail, white cards, cobalt), and attack (blue-charcoal, red, a narrow centred column with no brand mark) look like three products. The attack page has no FraudLens mark, and its header is plain text "FraudLens · Attack console".
- **Pill chips everywhere.** The case page wraps almost every value in a tinted chip: priority, "Needs L2", "New", "Unreviewed", "High confidence", "L2", "Confirmed", "Declined". The status chips carry meaning; the rest dilute it.
- **Repeated content on the case page.** The agent brief and "Why this payment was flagged" list the same four reasons verbatim, one under the other (1280 px).
- **Dashboard chart.** "Recent payment activity" shows four empty `0` columns and two blue bars, and labels every bar with a monospace number; most of the panel is empty.
- **Edge-flung footers.** The landing footer and the console footer ("FraudLens · Decisions backed by an auditable record." left, "UPI / Net banking / Cards / ATMs" right) place two clusters at the far edges with nothing on the axis between.
- **Hairline-ruled stat row.** Landing "Payment channels 4 / Scam typologies 4 / Precision 0.8462 / Backend tests 232" uses a cobalt top rule on each stat: the accent-bar card pattern.

## What already works (keep)
- No horizontal overflow at 375, 768, 1024 or 1440 px on landing and attack; none at 390 or 1280 px on dashboard and case.
- One icon system (Phosphor, `@phosphor-icons/react`), no emoji, no stock images, no gradient text, no glow, no glass.
- A real signature object exists: the Three.js lens with payment paths. It needs to be restyled, not replaced.
- Reduced-motion handling in all four stylesheets; content is visible without animation.
- Status colours are paired with text labels (C5); money uses tabular figures; IDs use a monospace.

## Top 5 fixes by visual impact
1. **One palette, one accent, no blue** (C1, C2, L4). Replace cobalt, navy and blue-charcoal with the chosen graphite + accent palette, defined once in `tokens.css`. The attack page sits on the dark side of the same palette.
2. **A locked type system** (T1, T2, T5, C3). Three or four weights, a ratio scale with a 12 px floor for running text, a display treatment for the landing that the console's headings echo.
3. **Recompose the landing** (L1, L2, L3). Break the left-stack hero, drop the kickers and the two-tone headline, give each section its own composition, and make the role section show hierarchy, not four equal cards.
4. **Surface roles** (R1, L4). Three radii (control, surface, chip), tonal elevation instead of white boxes on grey, and no hard section seams.
5. **Calmer case page** (C3, page findings). Fewer chips, no duplicated reasons, readable disabled buttons, minimum 12 px for evidence text.
