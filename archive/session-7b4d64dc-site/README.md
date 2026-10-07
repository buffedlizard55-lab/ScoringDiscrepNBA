# Archived site — prior session (PR #2, merged 2026-10-07)

This directory preserves **byte-identical** the GitHub Pages site built by the earlier
`arena/7b4d64dc-scoringdiscrepnba` session (PR #2, commit `060be50`), which lived at `docs/`
before the merge with PR #3, plus that session's original README (`ORIGINAL-README.md`).
Nothing here is modified. To view the archived site:

```bash
cd archive/session-7b4d64dc-site && python3 -m http.server 8080
```

It reads its bundled `data.json` / `statistics.json` / `latest_check.json` (also preserved here),
so it works standalone.

## Why archived instead of served

The repository can serve only one site from `docs/`. The PR #3 site (`docs/index.html`) was
kept as the served site because it was verified end-to-end in-session against the canonical
`data/cases/` store (all fetches 200, JS syntax-checked, data mirrors tested in-sync).

## Relationship to the canonical store

- Canonical, line-by-line-verified case store: `data/cases/*.json` (+ `data/cases.json`).
- This archived site's data: `data/discrepancies.json` (kept in place at that path, NOT deleted).
- The next session should verify the valuable leads in `data/discrepancies.json` that are missing
  from `data/cases/` (1978 NJN@PHI; 1969/1971/1952 protests; 2026 scorebugs; Porter correction)
  and promote each into `data/cases/` only with fresh, independently checked sources
  (the 2017 Robinson III case is the template — lead from PR #2, re-verified). See `ROADMAP.md` §5.

## Audit flags on the archived data (see `VERIFICATION.md` §6 for the full log)

1. `DISC-20241107-CLE-WAS-001` is dated **2024**-11-07, but its own cited Athletic URL is
   `/2025/11/08/` and Tre Johnson was drafted in 2025 — the canonical record dates the game
   **2025**-11-07. Year + case ID need correction. Do not cite.
2. RESOLVED 2026-10-07 in the archived session's favor: the league's own records confirm
   **only six protests ever upheld**, correcting the canonical store's earlier USA Today-based
   “3 since 1952” note. The per-case facts for the four pre-1982 protests remain unverified leads.
3. `research/README.md` lists 12 case files but only one `research/DISC-*.md` exists.

Logged: 2026-10-07 merge of PR #3.
