# UNESCO → UN: Global Rename + Transcript Integration

**Date:** 2026-04-26  
**Status:** Approved  
**Approach:** Surgical rename + transcript integration (Approach 1)

---

## Problem

1. The "UNESCO" label is misleading — the agent represents the **United Nations** mediator, not specifically UNESCO.
2. The `UNESCOMediatorCard` renders as a separate static panel disconnected from the debate flow (visible glitch in screenshot).
3. UN's closing statement should appear **inside** the debate transcript, not as an isolated card.

## Design Decisions

| Decision | Choice |
|----------|--------|
| UN transcript styling | **Gold/amber** bordered message block, same layout as other agents, with "UN MEDIATOR" badge |
| Authority citations | **Expand on tap** — clean by default, citations slide in when user clicks "View mandate" |
| Implementation approach | Modify existing `UtteranceRow` with conditional UN styling (not a new component) |

---

## Phase 1: Backend Rename (Python)

**Files:** `server.py`, `debate_orchestrator.py`, `environment.py`, `persona_loader.py`, `tasks.py`, `models.py`, `live_data.py`, `crisis_types.py`, `inference.py`, `graders.py`, `pytorch_scorer.py`

- All agent ID strings `"UNESCO"` → `"UN"`
- Class `UNESCOMediator` → `UNMediator`
- Variable `AGENT_IDS_NON_UNESCO` → `AGENT_IDS_NON_UN`
- API route `/unesco-authority/{crisis_type}` → `/un-authority/{crisis_type}`
- `AGENTS_CONFIG` entry: `id: "UN"`, `name: "United Nations"`, `tint: "#eab308"`
- Canned debates: all `_u("UNESCO", ...)` → `_u("UN", ...)`
- Speaker ordering logic: `"UNESCO"` checks → `"UN"` checks
- Vote tally exclusion: `"UNESCO"` → `"UN"`

## Phase 2: Data File Rename

- `personas/UNESCO.md` → `personas/UN.md` (update internal content: "UNESCO" references → "United Nations" where appropriate, keep UNESCO convention citations as legal references)
- `data/unesco_authority.json` → `data/un_authority.json`
- `data/relationships.json`: rename all `"UNESCO"` keys → `"UN"` in the matrix

## Phase 3: Frontend Single Source — `agents.js`

```js
{ id: 'UN', name: 'United Nations', code: 'UN', tint: '#eab308', lat: 48.85, lon: 2.35 }
```

- `STANCE_MAP.mediate`: update color from teal (`#14b8a6`) to gold (`#eab308`)

## Phase 4: Kill UNESCOMediatorCard

- **`chamber.jsx`**: Delete `UNESCOMediatorCard` component, delete `UNESCOLaurel` SVG component. Keep `ChamberView`, `LayoutModeToggle`, `RhetoricColdWarAlert`.
- **`WorldPolicy V6.1.html`**: Remove the `UNESCOMediatorCard` rendering block (lines ~303-312). Remove `debate.unescoUtterance` usage.
- **`debate-sim.jsx`**: Remove `unescoUtterance` from state. Remove the `if (u.speakerId === 'UNESCO')` block that sets it. Remove `heritageAtRisk` state (only used by the card).
- **`portraits.jsx`**: Remove `UNESCOLaurel` SVG component and its usage. UN gets a standard gold circle like other agents.

## Phase 5: UN Transcript Styling — `debate.jsx`

Modify `UtteranceRow` to detect `u.speakerId === 'UN'`:

### Visual changes:
- **Left border**: Gold `#eab308` (automatic via tint)
- **Background**: Subtle gold wash `rgba(234, 179, 8, 0.03)` always on (not just when active)
- **"UN MEDIATOR" badge**: Gold pill next to speaker name (`font-mono`, 8px, gold border)
- **Top divider line**: Thin gold gradient line above UN's row (like the old card had)

### Expandable citations:
- If `u.authorityCitation` truthy, show a "View mandate ▸" toggle below the message
- On click, expand a chip row: split `authorityCitation` on `;`, render each as a gold-tinted chip
- Show `WITHIN MANDATE ✓` (green) or `ADVISORY` (amber) badge inline

### No changes to:
- TypewriterText behavior (same word-by-word reveal)
- StancePill rendering (uses STANCE_MAP which is already updated)
- ThinkingIndicator (uses agent tint, now gold)

## Phase 6: Remaining Frontend Files

- **`pnl.jsx`**: `isUNESCO` → `isUN`, `'UNESCO'` → `'UN'`
- **`panels.jsx`**: `speakerId === 'UNESCO'` → `'UN'`, label `UNESCO AUTHORITY INVOKED` → `UN AUTHORITY INVOKED`, `unescoCite` → `unCite`
- **`sim.jsx`**: Any UNESCO string references → UN
- **`debate-sim.jsx`**: Arc derivation, any remaining UNESCO checks
- **`globe.jsx`**: Verify no hardcoded UNESCO (confirmed clean)

## Phase 7: README Update

- Global find-replace UNESCO → UN/United Nations in README.md
- Update architecture diagram, honesty table, feature descriptions

## Out of Scope

- `train.ipynb` — training notebook, separate concern
- Historical log/design `.md` files — archives, not runtime code
- `worldpolicy.css` — no UNESCO references exist

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Missing a reference causing runtime `KeyError` | Grep audit after all changes; syntax check all Python files |
| Breaking SSE contract (frontend expects "UNESCO") | Frontend and backend renamed simultaneously; no mixed state |
| `relationships.json` key mismatch | Automated JSON key rename |
| Persona loader can't find `UN.md` | File rename + path update in `persona_loader.py` |

## Acceptance Criteria

1. Zero occurrences of `UNESCO` in any runtime file (Python, JS, JSX, HTML, JSON) — except inside UNESCO convention citation *text content* (legal references like "WHC-1972")
2. UN's utterances appear in the debate transcript with gold styling and "UN MEDIATOR" badge
3. No `UNESCOMediatorCard` anywhere in the UI
4. Authority citations expand on tap in the transcript
5. Globe shows UN marker in gold at Paris
6. All canned debates work with `UN` agent ID
7. Live Groq debates work with `UN` agent ID
