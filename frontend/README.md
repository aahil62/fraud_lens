# FraudLens console

Next.js 16 (App Router), React 19 and TypeScript. Start it with the backend through `scripts/dev.py` from
the repository root (see the root README); `npm run dev` alone has no API to talk to.

| Path | Contents |
| --- | --- |
| `app/` | Routes: the landing (`page.tsx`), `/login`, `/signup`, `/attack`, and the signed-in console under `(console)/`. `tokens.css` is the only file with raw colours. |
| `components/landing/` | The landing page sections, the Three.js lens (`LensScene.tsx`, `lensModel.ts`) and its SVG fallback. |
| `components/console/` | The console shell: sidebar, top bar, search dialog. |
| `components/operations/` | Case workspace, decisions and approvals, fund trail, evidence graph, tables, and one file per console view in `views/`. |
| `lib/` | API client (`operations.ts`), shared types, the role table (`roles.ts`, kept equal to the API's by a backend test), formatting, session handling. |
| `proxy.ts` | Sends visitors without a session from console pages to `/login`. |
| `scripts/fetch-fonts.mjs` | Downloads Tanker and Erode into the gitignored `public/fonts/` before `dev` and `build`. |

```bash
npm run test          # vitest
npm run lint          # eslint
npx tsc --noEmit      # types
npm run format:check  # prettier
```
