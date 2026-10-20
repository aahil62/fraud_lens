# FraudLens visual overhaul

User direction: overhaul the landing page and every interface; use Scrollcraft and Three.js. Existing functionality and synthetic-data evidence boundaries remain. Creative choices below are authored implementation decisions, not invented user preferences.

## Direction
A daytime analyst workbench: bright white reading surfaces, pale blue mineral canvas (#f5f7fb), neutral charcoal navigation (#171b24), cobalt (#4058d5) for selected actions, and red/amber/green reserved for actual outcomes. Display uses locally bundled Mona Sans with a deliberate wide heavy setting on the landing page. Console uses the same family at compact, readable sizes. Numbers use tabular figures; code references use system monospace.

The signature is a dimensional signal lens: four payment streams enter an optical assembly, suspicious activity separates into a review path, and an analyst closes the loop. The 3D object belongs on the landing page; the console earns movement through data/state transitions rather than ambient spinning scenery.

## Shared contract
Root handles `globals.css`, ConsoleShell, login/signup, layout/fonts, Primitives and case detail styling. Landing owner handles `app/page.tsx`, new `components/landing/*`, and `app/landing.css`. Console-view owner handles `OperationsViews.tsx`, `ScenarioControls.tsx`, new view-only components and `app/workspace-views.css`. Do not edit each other's files.

Root CSS variables: --canvas #f5f7fb; --surface #fff; --surface-alt #f0f3fa; --ink #202635; --muted #626d80; --line #e3e7ef; --accent #4058d5; --accent-soft #edf0ff; --good #207657; --bad #b33e42; --warning #976314; --radius-panel 16px; --radius-control 9px. Existing legacy variables alias these. Font --font-sans: 'Mona Sans Variable', system-ui, sans-serif.

## Page goals
Landing: a composed 3D opening, varied scroll narrative, working channel/scenario controls, meaningful final entry action. No fake performance figures or clients. Console: icon navigation, clear breadcrumbs and session, dashboard with real status composition + channel chart + priority queue + activity, polished investigation/transaction ledgers, evidence graph, bank acknowledgement/state, reports, searchable audit and structured guidance. Case detail: stronger overview, reasons, signal contributions, prominent analyst action, related records and timeline. Auth pages: coherent full-page composition and readable forms.

## Verification plan
1. Inspect existing routes and define shared tokens; preserve provider/API contracts.
2. Implement independent landing and console views with shared shell, forms and tables.
3. Run frontend tests, lint and production build; review errors and fix.
4. Inspect every route in browser, including mobile and reduced-motion/fallback states; exercise filters, navigation, scenario, verdict and report interactions.
5. Save screenshots and update archive/patch and handoff notes. Backend logic remains unchanged.
