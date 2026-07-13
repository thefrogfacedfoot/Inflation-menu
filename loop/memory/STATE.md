# STATE

## environment
- 2026-07-13: preflight by build agent. Host: macOS 13.7.8 (x86_64), Darwin 22.6.0.
- Repo: standalone clone of thefrogfacedfoot/Inflation-menu at /Users/erwenchen/agentic_OS (fresh `git init` + fetch; the accidental home-directory git repo at /Users/erwenchen was left untouched by user decision).
- Test command 1: `cd sapient_app && python3 -m pytest -q` — 17 passed (needed pip --user installs: sapient_app/requirements.txt, pytest 8.4.2, eval_type_backport for py3.9 PEP-604 unions).
- Test command 2: `cd dashboard && npx tsc --noEmit` — clean (npm ci run 2026-07-13, node v20.20.2).
- The Python research core (scrapers, index_builder, granger) has NO test suite per project docs; verify.sh covers sapient_app + dashboard only.
- Tools: git 2.x, gh (auth OK, account thefrogfacedfoot), make, crontab, jq 1.7.1 (installed to ~/.local/bin), llm 0.27.1 + llm-anthropic plugin (pip --user, symlinked to ~/.local/bin), claude CLI (logged in).
- llm has NO stored API keys. Runtime plan: scripts source the repo .env for ANTHROPIC_API_KEY; cheap model = claude-haiku-4-5. Unverified until first real call — user forbids inspecting .env, so a missing key surfaces as a visible call failure, never assumed.
- Mail transport binaries exist (/usr/bin/mail, postfix, sendmail); actual delivery NOT verified — see CRON.md.
- python3 is system 3.9.6; pip --user scripts land in ~/Library/Python/3.9/bin (llm, pytest symlinked into ~/.local/bin for cron PATH).

## recent
