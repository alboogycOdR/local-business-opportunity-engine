# LBOE Operator Console — UX & Accessibility Recommendations

**Audited commit:** `cc56bda` · **Workstream:** WS-O · **Evidence:** `audit/evidence/ui/` (baseline) and
`audit/evidence/ui-patched/` (after patches) · **Regression tests:** `audit/tests/test_ux.py`

## 1. What an operator experiences today (baseline)

Starting from a fresh campaign, an operator can discover or import leads, score them, prepare a brief and generate a
concept preview **only through the UI**. After that the console stops. There is no control anywhere to approve a
concept, draft outreach, record the consent decision, record a manual contact, log a reply, or add a follow-up. The
dashboard still tells them to "Review demos", and the Demo review queue links to a business page with no review
control. Everything after `REVIEW_PENDING` requires hand-written JSON calls to `/v1`. These are exactly the steps the
product's safety promise depends on: human review, consent, and recording who decided what.

Five other experiences stand out:

1. **A suppressed lead looks like a live one.** The page recommends "Review a conversion upgrade" with a *Run
   optional enrichment* button, says *"No identity, suppression, or policy holds are blocking this lead"*, and shows
   a *Verified identity* badge. A small grey "Suppressed" pill is the only signal
   (`evidence/ui/business-suppressed-stale-score-desktop-1440.jpg`).
2. **The prospect sees an unstyled page.** The concept preview links `styles.css`, which no route serves (404 on
   both `/preview/<token>` and the internal preview). A prospect gets browser-default Times text with
   "Booking placeholder / WhatsApp placeholderCall placeholder" links to anchors that don't exist
   (`evidence/ui/prospect-preview-mobile-390.jpg`).
3. **A third of concept previews fail QA for reasons the operator can't fix.** Names with `&` or `'` fail
   "business name present", because the check compares against HTML-escaped text. Text such as "Hair 2 Go",
   "Floor 1" or "concept for 12 Kloof Street" fails "no fake prices", because the regex `(?:\$|r)\s?\d+` matches the
   *r* at the end of *for*, *Floor* and *Hair*. Measured: **17 of 51 generated demos (33%)** failed only for these
   reasons (`evidence/LBOE-AUD-UX/demo_qa_false_failures.txt`).
4. **Refused actions show raw JSON.** Examples are `{"detail":"demo_not_shareable"}`, a Pydantic error array, or a
   bare `Internal Server Error` (`evidence/LBOE-AUD-UX/error_pages.txt`).
5. **Times are wrong for a Cape Town operator.** A follow-up due at 09:00 SAST is shown as
   `2026-10-02 07:00:00+00:00`, and on SQLite, or on a Postgres server not set to UTC, as 11:00. Queues use raw UUIDs
   as link text.

## 2. Measured accessibility baseline and result

Playwright + axe-core 4.13 (WCAG 2.0/2.1/2.2 A and AA plus best practice) was run on 45 pages at 4 viewports
(1440×900, 1024×768, 768×1024, 390×844). axe ran at 1440 and 390; that is 90 page scans.

| axe rule | Impact | WCAG | Baseline (pages / nodes) | After patches |
|---|---|---|---|---|
| `color-contrast` | serious | 1.4.3 AA | 43 / 482 | **0** |
| `select-name` | critical | 4.1.2 A | 8 / 16 | **0** |
| `label` | critical | 4.1.2 A | 4 / 12 | **0** |
| `scrollable-region-focusable` | serious | 2.1.1 A | 5 / 5 | **0** |
| `region` | moderate | best practice | 43 / 86 | **0** |
| `empty-table-header` | minor | best practice | 2 / 4 | **0** |

| Probe (custom) | Baseline | After |
|---|---|---|
| Form controls with no accessible label (placeholder-only counts as unlabeled) | 36 | **0** |
| Interactive targets < 24×24 px at 390 px (WCAG 2.2 SC 2.5.8) | 574 | **0** |
| Pages with more than one `<h1>` | 10 | **0** |
| Skip link / first Tab stop | none / "LBOE Operator Cockpit" | **"Skip to main content"** |
| Raw UUIDs used as link text | 3 | **0** |
| Pages overflowing horizontally (390 / 768 / 1024) | 0 / 0 / 1 | **0 / 0 / 0** |
| Concept preview (axe on saved HTML, both viewports) | 0 violations | 0 violations |

Root causes of the contrast failures were three tokens: `--muted` #6d7788 on the page background (4.16:1),
`--blue` links (3.89:1) and the coral eyebrow text (2.37–2.58:1). They were darkened to #636c7b (4.88:1),
#4b64cc (4.84:1) and a new `--coral-ink` #aa513f (4.89:1); the palette is otherwise unchanged
(`evidence/LBOE-AUD-UX/contrast_ratios.txt`).

**Positive findings to keep:** `lang` is set on every page; there is visible focus (3 px outline) on every Tab stop;
no page overflows at 390 px in the baseline; POST actions redirect with 303 (Post/Redirect/Get), so refresh never
re-submits; and the concept preview markup itself has zero axe violations.

## 3. Defect list (prioritised)

Status: **Fixed** = fixed by a patch in `audit/patches/` with a regression test that fails on `cc56bda`.
**Open** = recommendation only.

| ID | Defect | Severity | Status |
|---|---|---|---|
| LBOE-AUD-110 | Human-gated steps (concept review, drafts, consent, contact log, CRM outcome, follow-up) have no UI; the golden path cannot be completed in the console | **Critical** | Fixed (`ui/workflow.py`; golden-path test drives every step through forms only) |
| LBOE-AUD-111 | Suppressed lead shown as actionable ("no holds", enrichment CTA, verified badge) | **High** | Fixed (`role=alert` banner, actions removed, holds include suppression) |
| LBOE-AUD-112 | Prospect preview unstyled (CSS 404), dead placeholder anchors, indexable and cacheable, token leaks via Referer | **High** | Fixed (self-contained HTML, `noindex` meta + `X-Robots-Tag`, `no-store`, `no-referrer`, strict CSP; existing demos inlined at serve time) |
| LBOE-AUD-113 | Demo QA false failures on `&`, `'`, "r"+digit; demo ignored the brief's address label | **High** | Fixed (copy rules run on generated text only; names compared unescaped; `Address/locality` label honoured) |
| LBOE-AUD-114 | Text contrast below 4.5:1 on 43 pages | **High** (WCAG AA) | Fixed |
| LBOE-AUD-115 | Placeholder-only / unlabeled form controls, including primary forms | **High** (WCAG A) | Fixed |
| LBOE-AUD-116 | No skip link; duplicate `<h1>`; content outside landmarks; `<th>` without scope; unfocusable scroll regions | **Medium** | Fixed |
| LBOE-AUD-117 | Mobile nav links about 17 px tall (574 undersized targets) | **Medium** (WCAG 2.2 AA) | Fixed |
| LBOE-AUD-118 | UUIDs as link text (follow-up, proposal-ready, my-queue, assignments, "Demo &lt;uuid&gt;") | **Medium** | Fixed |
| LBOE-AUD-119 | Times shown as raw UTC ISO with microseconds; aware datetimes stored without UTC normalisation (wall-clock drift) | **High** (wrong data shown) | Fixed (`UtcDateTime` type, Postgres session pinned to UTC, `LBOE_DISPLAY_TIMEZONE`, default Africa/Johannesburg) |
| LBOE-AUD-120 | UI errors render as raw JSON or 500; share form offered for unshareable demos; comment on unknown business → 500 on Postgres / orphan row on SQLite | **Medium** | Fixed (HTML error pages for `/ui`, neutral page for `/preview`, JSON kept for `/v1`) |
| LBOE-AUD-121 | Misleading copy: hard-coded "Verified identity"; "Approved concepts are waiting…" for unreviewed concepts; dry-run banner claims logging is "blocked" (it is not enforced) | **Medium** | Fixed (copy); enforcement of dry-run is **Open** |
| LBOE-AUD-122 | Dashboard "Failed / blocked jobs" always 0 (reads report keys that do not exist) | **Medium** | Fixed |
| LBOE-AUD-123 | "Recommended next step" ignores lifecycle stage (tells an outreach-ready lead to run enrichment) | **Medium** | Fixed |
| LBOE-AUD-124 | Campaign list silently hides every older campaign with the same name, vertical and geography; their leads become unreachable from the list | **Medium** | Open |
| LBOE-AUD-125 | Raw lifecycle and action codes (`APPROVED_FOR_OUTREACH`, `conversion_upgrade_offer`) in tables and filters: 272 occurrences, 197 left after the patch (campaign lead table, queues, report tables) | Low | Partly fixed (business page, badges and statuses use labels; `presentation.state_label`/`action_label` are ready to apply to the rest) |
| LBOE-AUD-126 | Destructive actions without confirmation or preview of consequence: *Suppress business* (permanent), *Revoke*, *Close pilot*, bulk suppress | Medium | Open |
| LBOE-AUD-127 | Long synchronous actions (audit up to 2 × 30 s page loads, discovery up to 300 s) with no progress feedback; a double-click resubmits | Medium | Open |
| LBOE-AUD-128 | Proposal review UI approves with all safety checks hard-coded true; delivery pages render no forms for the checklist, milestone and approval POST routes | Medium | Open |
| LBOE-AUD-129 | Google Maps iframe on every dashboard and campaign load sends the campaign query and operator IP to Google; with no API key, offline, or when blocked it shows an empty grey frame, and the overlay card covers the map centre | Low | Open |
| LBOE-AUD-131 | Share links issued before a suppression keep serving the concept to the prospect | **High** | Fixed (suppression revokes links; `/preview` also refuses suppressed businesses and non-shareable demos) |
| LBOE-AUD-130 | Sticky header plus a wrapped 10-item nav takes about 25% of a 390×844 viewport on every page | Low | Open |

## 4. Redesign recommendations

### R1. One "Next decision" rail per lead (implemented in the patch)

The lead page should answer three questions top to bottom: *where is this lead*, *what must I decide now*, and
*what evidence supports it*. The patch makes the hero stage-aware (LBOE-AUD-123) and adds a single
**Next human decision** section that renders only the forms valid for the current state.

```
┌ Atlantic Styling · Barber shop · Sea Point ───────────── [Cleared for manual contact] ┐
│ RECOMMENDED NEXT STEP                                                                  │
│ Contact them yourself, then record it                        [ Record contact ↓ ]      │
│ LBOE never sends. Use the approved draft outside LBOE and record what you did.         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Score 44 · Evidence ready · Outreach drafted          (evidence, score details below)  │
├ Next human decision (#workflow) ───────────────────────────────────────────────────────┤
│ Message used   [ Email draft ▾ ]     When you sent it [ 29 Sep 2026 18:22 ]           │
│ Your name      [ Lab Operator   ]    Notes [                          ]                │
│ [ Record manual contact ]                                                              │
│ ── Schedule a follow-up:  What [           ]  Due [            ]  [ Add follow-up ]    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### R2. Make consent a deliberate, explained decision (implemented)

The consent form has no default basis: the first option is an empty "Choose…", and the select is `required`. It
says in words that listing details are not consent, requires evidence text for the chosen basis, and uses radio
buttons for *Clear for one manual contact / Do not contact now / Suppress permanently*. **Next step (open):** show
the exact draft text and channel being cleared next to the decision, and record the decision against a
per-operator login instead of a typed name.

### R3. Suppression is a terminal, loud state (implemented)

```
┌───────────────────────────────────────────────────────────────────────┐
│ ⛔ Suppressed — do not contact. Reason: owner opted out · 29 Sep 2026   │
│   Scoring, demos, drafts and contact logging are disabled.            │   role="alert"
└───────────────────────────────────────────────────────────────────────┘
RECOMMENDED NEXT STEP: Suppressed — do not contact   (no buttons)
```

Suppression now also **withdraws the business's share links**: at baseline a link issued before suppression kept
serving the concept (`evidence/LBOE-AUD-UX/preview_after_suppression.txt`), and the patch revokes the links and
refuses to serve them (LBOE-AUD-131). **Next step (open):** a confirmation step that states the consequence before
suppressing.

### R4. Queues as an inbox, not a link list

Today `/ui/queues` shows six count cards and each queue is an unstyled `<ul>`. Recommended layout:

```
Queues                                              Filter: [Campaign ▾] [Assigned to me ☐]
┌──────────────────────────┬───────┬────────────────────────────────────────────────────┐
│ Awaiting concept review  │  12   │ Oldest: Anne's Hair & Beauty · 3 days               │
│ Consent decisions        │   4   │ Oldest: Fynbos Beauty · today                       │
│ Cleared — contact & log  │   2   │                                                     │
│ Replies to log           │   7   │ 2 overdue follow-ups                                │
└──────────────────────────┴───────┴────────────────────────────────────────────────────┘
Awaiting concept review
 Business ↑        Locality     Score  Concept created   QA   Assigned   [Review]
 Anne's Hair …     Woodstock    48     29 Sep 15:36      ✓    Lab Op.    [Review →]
```

Each row should link straight to `#workflow`, with sortable columns, "assigned to me", age, and names instead of IDs.

### R5. Campaign lead table: paginate, sort, filter by meaning (pagination implemented)

The patch adds 50-row pages with Previous/Next (the baseline rendered every lead: a 12,000 px page for 100 leads
at 1024 px). **Next (open):** replace the free-text `State` / `Recommended action` / `Score band` inputs, which
require typing internal codes, with selects that use `state_label` / `action_label`; add column sorting; show state
and action as human labels.

### R6. Mobile navigation

At 390 px the 10-item nav wraps to three lines inside a sticky header. Recommended: a compact header with a
*Menu* disclosure (a `<details>` element works without JavaScript) and a four-item bottom bar: **Queues ·
Opportunities · Campaigns · More**. Operators in this market work from phones between visits.

### R7. Long-running actions

Audit, discovery and enrichment run inline in the request, for up to minutes. Minimum: disable the submit button
and show "Auditing website — this can take up to a minute" (a small progressive-enhancement script, or a
`<form>` that posts to a job endpoint and redirects to a status page with `<meta http-equiv=refresh>`). Better:
move these into the Redis worker the architecture already describes and show job status on the lead page.

### R8. Prospect-facing preview (implemented, with follow-ups)

The patch serves a self-contained, styled, `noindex`, non-cacheable page under a strict CSP. It gives the
"Independent concept preview" banner a visible yellow panel, and the nav links point to real sections.
**Follow-ups (open):** add a visible "Not interested? Reply STOP to the person who sent this" line; show the
sender's name and business so the prospect knows who prepared it; and let operators preview exactly what the
prospect will see before sharing.

### R9. Errors that say what to do (implemented)

`/ui` errors render inside the console with a sentence mapped from the API code (for example: "Only concept
previews that passed QA can be shared. Fix or regenerate this concept first."), plus *Go back* and *Dashboard*
links. `/preview` errors render a neutral, unbranded page ("This preview link has expired or has been withdrawn"),
so a prospect never sees the operator console chrome. `/v1` keeps FastAPI's machine-readable JSON, as the
architecture requires.

## 5. Keep server-rendered HTML, but move it to templates

**Recommendation: keep server-side rendering, move the ~2,300 lines of f-string HTML into Jinja2 templates with
autoescaping, and add progressive enhancement where needed, e.g. htmx-style partial updates for the workflow rail
and job progress. Do not build the separate SPA stubbed in `apps/operator-web` for v1.**

Reasons, grounded in this audit:

- **Every fix in this pass was a server-side change**, and none needed client state. The accessibility failures
  were markup and CSS; the workflow gap was missing forms; the performance problems were queries.
- **Safety gates live in the API functions.** Server-rendered forms that call those same functions (the
  `ui/workflow.py` pattern) keep one enforcement point. An SPA would add a second client that must re-implement
  the "what is allowed now" logic.
- **The operator base is small, often on phones and variable connections.** Measured `/ui` pages are 1–90 KB with no
  JavaScript bundle; the patched pages score 0 axe violations without any JavaScript.
- **Templates fix the real maintainability risk.** Escaping is applied by hand at about 208 call sites
  (189 `esc()`, 19 `html.escape()`). Autoescaping makes the safe path the default, and makes pages reviewable by designers.

Suggested migration, one page per PR, each covered by the audit tests:

| Step | Size |
|---|---|
| Add a Jinja2 environment; move `page()` to `base.html` | S |
| Business page and workflow rail | M |
| Queues, campaign and opportunities | M |
| Pilots, proposals, delivery, admin | M |
| Delete the f-string helpers | S |
