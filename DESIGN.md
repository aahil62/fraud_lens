# FraudLens design system

## Intent

A daylight workbench for an analyst comparing evidence on a laptop. White reading surfaces separate records from a mineral-blue canvas; charcoal navigation anchors the workspace. Cobalt denotes the current action or selection. Outcome colors carry operational meaning. The landing page turns that same language into an optical assembly through which payment streams pass.

## Tokens

| Role | Value |
| --- | --- |
| Canvas | `#f5f7fb` |
| Reading surface | `#ffffff` |
| Alternate surface | `#f0f3fa` |
| Primary ink | `#202635` |
| Secondary text | `#626d80` |
| Structure | `#e3e7ef` |
| Selected / primary action | `#4058d5` |
| Selected surface | `#edf0ff` |
| Navigation | `#171b24` |
| Confirmed / posted | `#207657` |
| Failure / fraud / declined | `#b33e42` |
| Pending / review | `#976314` |

Authoritative CSS: `frontend/app/globals.css`; view-specific styles: `workspace-views.css`; landing choreography: `landing.css`.

## Type and shape

Mona Sans Variable is bundled locally through its OFL npm package. The landing uses a wide, heavy display setting; the console uses compact medium-weight headings and readable neutral labels. Money uses tabular figures; opaque references use system monospace. Surfaces use 16px corners, controls 9px, and status labels 5px. The overlapping-lens brand mark is shared visually across the landing, auth and console.

## Layout and interactions

- Desktop: 224px charcoal rail, compact breadcrumb/session header, subtle simulation disclosure, and a flexible content canvas.
- Mobile: navigation becomes a focus-contained drawer, main content is inert while open, Escape closes, and focus returns to the trigger.
- Tables keep full records in a horizontal scroll region, with filters and pagination outside it. No viewport-wide overflow.
- Search uses a native dialog with keyboard and Escape support. Results identify the bounded recent-case scope.
- Reports expose export formats; operational filtering never changes the underlying global counts.
- Evidence graphs show actual references, distinct node types, keyboard inspection and a full-text link list. Layout is schematic, not a geographic or quantitative position claim.

## Motion and depth

The landing uses unchanged Scrollcraft progress and a purpose-built Three.js lens: layered hardware, optical rings, four paths and moving packets. Scroll and fine-pointer input adjust perspective; channel selection carries through to a sample incident. A complete SVG fallback remains when WebGL is absent or reduced motion is requested. Offscreen and hidden-page rendering stops; all GPU resources are disposed on cleanup. Working screens avoid decorative 3D and long page entrances. Content is visible by default.

## Evidence and maintenance

Use semantic controls, visible focus, 4.5:1 text contrast, clear error/loading/empty states, compact-phone checks, and reduced-motion alternatives. A screenshot or green unit test alone does not certify accessibility or performance. See the redesign verification record for the actual checked routes and interactions. Keep example data and operational metrics clearly separate; never add fake customers, savings, trends, accuracy or compliance badges.
