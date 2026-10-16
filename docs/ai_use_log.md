# AI-use log

This is a factual record of how AI tools were used in this project. It is compiled from evidence that can be checked, and every statement names its source. Where the evidence does not reach, this log says so; it does not guess.

Compiled 2026-10-16, by Claude Code (Anthropic) at WC's request. WC is to review it.

## 1. Evidence sources and their coverage

| Source | What it shows | Coverage |
|---|---|---|
| Claude Code session transcripts, archived **outside the repo** at `~/uifpi_private/sessions/` | Every prompt WC typed, every command and edit Claude made, and every commit and merge Claude ran | Two sessions on 2026-06-17 (`4f3dcc62`, `f4c9be8a`). These were tracked in `sessions/` from `0fe4969` (2026-07-06) until they were untracked on 2026-10-16. A `SHA256SUMS` file sits beside them |
| Claude Code local session store `~/.claude/projects/-Users-erwenchen-Inflation-menu/*.jsonl` | Same content as above | Ten sessions, 2026-09-13 to 2026-10-16. **No transcripts exist for 2026-06-06 to 2026-09-12 apart from the two above.** Use of AI in that period is shown only by the PR and branch evidence below |
| GitHub PR bodies | The footer "🤖 Generated with Claude Code" | PRs #1–#60 |
| Branch names | `agent/*`, `agentic/*` and `wt-*`: names given by agent or worktree tooling | All branches |
| `blueprints/*.md` | Written task specifications for PRs #1–#6 | July 2026 |
| Commit trailers | `Co-Authored-By: Claude …` | **None before 2026-10-16.** Until then a repo rule (CLAUDE.md) forbade the trailer. It was removed on 2026-10-16 (this PR), and AI-assisted commits carry it from now on |

All commits are authored as `thefrogfacedfoot` (WC's account), including those Claude created. Git authorship therefore does not separate WC's commits from Claude's.

## 2. AI used inside the research pipeline (not development help)

| Script | AI service | What it does | Where its output goes |
|---|---|---|---|
| `nlp_pipeline.py` (`54decdf`, 2026-06-12) | Anthropic API, model `claude-sonnet-4-6` | Classifies menu item names into categories, quality signals and language | Table `nlp_results` (2,142 rows on 2026-10-16). It is LEFT-JOINed as `category` in `index_builder.load_price_data` and in `granger_analysis.py`. This log does not check whether `category` changes any headline number |
| `image_processor.py` (`7a512d0`, 2026-06-13) | Google Gemini Vision API, model `gemini-1.5-flash` | Extracts prices from menu photos listed in `image_log.csv` | Not traced in this log |

## 3. By component

**"PR footer"** means the PR body carries the Claude Code footer. **"gh merge by Claude"** means a `gh pr merge` call appears in an available transcript. Merges with no such call were made through the GitHub UI, or in a session with no surviving transcript; the two cases cannot be told apart.

| Component | First commit | AI evidence | WC: specified, decided or reviewed (evidence) |
|---|---|---|---|
| Live scraper `live_scraper.py` | `a3c3a03` 2026-06-07 | PR footers: #12, #24–#29 (TARGETS chunks), #38 (run-config logging), #41 (platform column), #48, #51. Branches `agent/pin-scraper-venv-interpreter` (#17) and `wt-7` (#18). gh merge by Claude: #24, #25, #26, #29, #38, #41 | Earliest commits (2026-06-07 to 06-09, e.g. `a3c3a03`, `baf7996`) predate any surviving transcript; no AI evidence exists for them either way. Concurrency rule and DoorDash exclusion are recorded as WC rules in CLAUDE.md |
| Wayback scrapers (`historical_scraper.py` `7fdc158`, `historical_html_scraper.py` `86e6ed6`, sweep scripts) | 2026-06-12 / 06-16 | Transcript `4f3dcc62` (2026-06-17/18) shows Claude implementing Wayback extraction and running sweeps. Branch `agent/resume-wayback-expansion-…` (#16). PR footer #12 | WC's prompts in `4f3dcc62` and `f4c9be8a` set the tasks. The rule "data integrity > volume" is WC's (quoted in `4f3dcc62`) |
| Index builder / Granger (`index_builder.py`, `granger_analysis.py` `54decdf`; `gap_robustness.py` `0fe4969`) | 2026-06-12 | PR footers #1–#6 (July fixes, with specs in `blueprints/`), #43 (provenance whitelist) | Headline choice: CLAUDE.md records F=4.20/p=0.0499 as the headline and the old figure as deprecated (WC rule). #43 merged with no gh merge call found |
| Official CPI ingestion (`get_monthly_cpi_all.py` `a673f46`; `official_cpi_prereg.py`) | 2026-06-13 | PR footer #44 | #44 merged with no gh merge call found |
| Dashboard and API (`dashboard/` `e89d2a2`, `api.py` `48e5534`) | 2026-06-13 / 06-14 | PR footers #2, #6, #59. gh merge by Claude: #59 (2026-10-16, on WC's written request "Redeploy, then confirm the live text") | WC asked on 2026-10-16 for the badge text change |
| Paper drafts (IRC-SET draft `paper_draft/…`; CJSJ submission) | IRC-SET draft prepared at `6609c83` 2026-07-13; CJSJ 2026-09-19 | PR footers #30–#37 (CJSJ figures, corrections, docx, verifier). Branches `wt-9` and `wt-10` (#21, #22). gh merge by Claude: #30–#36. Transcript `ef78b5ab` (2026-09-18 to 09-29) has 10 `git commit` calls | The paper text is WC's responsibility; how much of it Claude drafted is visible only in transcripts from 2026-09-13 onward. The CJSJ submission's own Acknowledgements already disclose Claude and Claude Code use (`paper_draft/cjsj/build_cjsj_docx.js`, line 182). For the July IRC-SET draft, which has no transcript, see §5 |
| Pre-registration v1 (`docs/preregistration.md` `d451406`, `prereg_analysis.py` `b35ce7d`) | 2026-10-07 | PR footers #39, #45, #46. gh merge by Claude: #39. Transcript `289794ab` (2026-10-07 to 10-14) | v1 records its decisions as WC's |
| Pre-registration v2 (`docs/preregistration_v2.md` `c5ccf1a`, `diagnostics/tax_feasibility/`) | 2026-10-10 | PR footer #52. Transcript `289794ab` | §10 of the document records each design decision as "WC decision" (revisions 2–5). §11 lists changes Claude made unrequested, "for WC to accept or revert". #52 was merged and tagged `prereg-v2` with no gh merge call found |
| Simulation study (`analysis/simulation/`) | 2026-10-15 (#55) | PR footer #55. Transcript `322c7d14`: Claude wrote all code, ran it and wrote the summary | WC specified the design (null model, N values, ρ grid, steps, α, multiplicity comparison, figure format) in the 2026-10-15 prompt |
| Data provenance (`docs/data_provenance.md`, `diagnostics/provenance/`) | 2026-10-16 (#57) | PR footer #57. Transcript `322c7d14`: Claude wrote the reconstruction method and the document, and added `prices.retrieved_at` to the local DB after a backup | WC asked for retrieval dates with evidence, and for a column "if cheap" |
| Scraper monitoring (`~/scraper_watch/`, launchd agents) | 2026-10-09 to 10-11 (#54) | PR footer #54. gh merge by Claude: #54. Transcript `289794ab` | — |
| Repo hygiene and disclosure (#47, #56, #58, #60, this PR) | 2026-10-08 to 10-16 | PR footers on all of them. gh merge by Claude: #47 | WC approved each removal item on 2026-10-16 |

## 4. Merges executed by Claude

Found in the available transcripts (2026-09-13 onward): #24, #25, #26, #29, #30, #31, #32, #33, #34, #35, #36, #38, #39, #41, #47, #54, #59.

Each ran as `gh pr merge` under WC's GitHub account. This log does not establish, merge by merge, whether WC asked for the merge in that session. The transcripts hold WC's prompts and can be checked.

## 5. WC's statement on the AI's role in the IRC-SET draft (July 2026)

> **PLACEHOLDER: WC TO WRITE. Do not fill in from AI output.** No transcript covers this draft (§1). This statement is WC's own account of what Claude drafted, edited or checked in `paper_draft/UICPI_A_Method_for_Collecting_Chain_and_Independent.md` (prepared at `6609c83`, 2026-07-13) and of what WC wrote or decided.

## 6. Commit metadata from 2026-10-16

From 2026-10-16, commits in this repository are authored with WC's GitHub noreply address (`187934484+thefrogfacedfoot@users.noreply.github.com`, repository-level `git config user.email`). AI-assisted commits also carry a `Co-Authored-By: Claude …` trailer. Earlier commits are unchanged; history is not rewritten.
