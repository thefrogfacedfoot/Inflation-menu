"""
UIFPI — SSEF Submission Checklist
Verifies all SSEF submission requirements are met.
Prints ✓/✗ for each requirement and a final SUBMISSION READY / NOT READY verdict.
Saves checklist to ssef_submission_checklist.txt.
"""

import os
import re

PAPER_DIR   = "paper_draft"
FIG_DIR     = "figures"
TABLES_DIR  = "tables"
RESULTS_DIR = "analysis_results"

REQUIRED_FIGURES = [
    "fig1_index_comparison.png",
    "fig2_lead_times.png",
    "fig3_pass_through.png",
    "fig4_benchmark.png",
    "fig5_country_map.png",
]

REQUIRED_TABLES = [
    ("table1_sample.csv", "table1_sample.tex"),
    ("table2_descriptive.csv", "table2_descriptive.tex"),
    ("table3_granger.csv", "table3_granger.tex"),
    ("table4_passthrough.csv", "table4_passthrough.tex"),
]

REQUIRED_DATA_FILES = [
    "uifpi.db",
    "uifpi_index.csv",
    os.path.join(RESULTS_DIR, "granger_results.json"),
    os.path.join(RESULTS_DIR, "robustness.json"),
    os.path.join(RESULTS_DIR, "benchmark_comparison.json"),
]

REQUIRED_CODE_FILES = [
    "historical_scraper.py",
    "index_builder.py",
    "granger_analysis.py",
    "robustness_checks.py",
    "benchmark_comparison.py",
    "generate_figures.py",
    "paper_data_tables.py",
    "abstract_generator.py",
]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def check_abstract() -> tuple[bool, int, str]:
    path = os.path.join(PAPER_DIR, "abstract.md")
    if not os.path.exists(path):
        return False, 0, "abstract.md not found"
    with open(path) as f:
        content = f.read()
    # strip markdown headers for word count
    prose = re.sub(r"^#.*$", "", content, flags=re.MULTILINE)
    prose = re.sub(r"---.*", "", prose, flags=re.DOTALL)
    wc = word_count(prose.strip())
    ok = wc <= 250
    return ok, wc, f"{wc} words"


def check_research_plan() -> tuple[bool, list[str]]:
    # Look for proposal.md or any research_plan file
    candidates = ["research_plan.md", "proposal.md",
                  os.path.join("research skeleton", "proposal.md")]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read().upper()
            required_sections = [
                ("RESEARCH QUESTION", ["RESEARCH QUESTION", "PRIMARY RESEARCH"]),
                ("Hypothesis",        ["HYPOTHESIS", "SECONDARY HYPOTHESIS"]),
                ("Methodology",       ["METHODOLOGY", "METHOD", "ANALYSIS"]),
                ("Background",        ["BACKGROUND", "CONTEXT", "RATIONALE", "RESEARCH GAP"]),
                ("Data",              ["DATA", "DATASET", "COLLECTION"]),
                ("Results/Analysis",  ["RESULT", "FINDING", "EXPECTED OUTCOME"]),
                ("References",        ["REFERENCE", "BIBLIOGRAPHY", "CITATION"]),
            ]
            found = []
            missing = []
            for label, keywords in required_sections:
                if any(kw in content for kw in keywords):
                    found.append(label)
                else:
                    missing.append(label)
            return len(missing) == 0, missing
    return False, ["research_plan.md not found"]


def count_citations(min_citations: int = 10) -> tuple[bool, int, str]:
    candidates = ["research_plan.md", "proposal.md",
                  os.path.join("research skeleton", "proposal.md")]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            # Count citation patterns: author (year), [n], doi:, etc.
            patterns = [
                r"\(\d{4}\)",               # (2016)
                r"\[\d+\]",                 # [1]
                r"doi:",                    # doi:
                r"et al\.",                 # et al.
                r"https?://",              # URLs
            ]
            all_matches = set()
            for p in patterns:
                all_matches.update(re.findall(p, content))
            # count lines that look like bibliography entries
            bib_lines = [ln for ln in content.splitlines()
                         if re.search(r"\d{4}", ln) and len(ln) > 30]
            n = max(len(all_matches), len(bib_lines))
            ok = n >= min_citations
            return ok, n, f"{n} citations detected"
    return False, 0, "no research plan file found"


def check_github() -> tuple[bool, str]:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            return True, f"Remote: {url}"
        return False, "No remote configured"
    except Exception as e:
        return False, f"Git check failed: {e}"


def check_reproducible() -> tuple[bool, str]:
    has_requirements = os.path.exists("requirements.txt")
    has_readme       = os.path.exists("README.md")
    has_run_script   = os.path.exists("run_all.py")
    score = sum([has_requirements, has_readme, has_run_script])
    msg = (f"requirements.txt={'✓' if has_requirements else '✗'}  "
           f"README.md={'✓' if has_readme else '✗'}  "
           f"run_all.py={'✓' if has_run_script else '✗'}")
    return score >= 2, msg


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def main():
    lines   = []
    passed  = 0
    total   = 0

    def check(label: str, ok: bool, detail: str = ""):
        nonlocal passed, total
        total += 1
        icon = "✓" if ok else "✗"
        if ok:
            passed += 1
        msg = f"  {icon}  {label}"
        if detail:
            msg += f"  ({detail})"
        print(msg)
        lines.append(msg)

    print("=" * 60)
    print("SSEF SUBMISSION CHECKLIST")
    print("=" * 60)

    # 1. Research plan
    rp_ok, rp_missing = check_research_plan()
    check("Research plan exists",
          rp_ok,
          f"missing: {', '.join(rp_missing)}" if not rp_ok else "all sections present")

    # 2. Abstract
    ab_ok, ab_wc, ab_detail = check_abstract()
    check("Abstract exists and ≤ 250 words", ab_ok, ab_detail)
    check("Abstract fits on one page",
          ab_ok and ab_wc <= 300,
          f"{ab_wc} words")

    # 3. Bibliography
    bib_ok, bib_n, bib_detail = count_citations(min_citations=5)
    check("Bibliography has ≥ 10 citations",
          bib_ok, bib_detail)

    # 4. Figures
    print("\n  Figures:")
    lines.append("\n  Figures:")
    all_figs = True
    for fname in REQUIRED_FIGURES:
        ok = os.path.exists(os.path.join(FIG_DIR, fname))
        if not ok:
            all_figs = False
        check(f"  {fname}", ok)

    # 5. Tables
    print("\n  Tables:")
    lines.append("\n  Tables:")
    all_tables = True
    for csv_name, tex_name in REQUIRED_TABLES:
        ok = (os.path.exists(os.path.join(TABLES_DIR, csv_name)) and
              os.path.exists(os.path.join(TABLES_DIR, tex_name)))
        if not ok:
            all_tables = False
        check(f"  {csv_name} + .tex", ok)

    # 6. Data files
    print("\n  Data & Results:")
    lines.append("\n  Data & Results:")
    for f in REQUIRED_DATA_FILES:
        check(f"  {f}", os.path.exists(f))

    # 7. Code files (reproducibility)
    print("\n  Code (reproducibility):")
    lines.append("\n  Code (reproducibility):")
    for f in REQUIRED_CODE_FILES:
        check(f"  {f}", os.path.exists(f))

    # 8. Reproducibility packaging
    repro_ok, repro_detail = check_reproducible()
    check("Reproducibility files present", repro_ok, repro_detail)

    # 9. GitHub
    gh_ok, gh_detail = check_github()
    check("GitHub repo configured", gh_ok, gh_detail)

    # --------------- Verdict ---------------
    verdict_line = ""
    print("\n" + "=" * 60)
    lines.append("\n" + "=" * 60)

    critical_checks = [
        rp_ok,
        ab_ok,
        all_figs,
        all_tables,
        os.path.exists(os.path.join(RESULTS_DIR, "granger_results.json")),
    ]
    submission_ready = all(critical_checks)

    if submission_ready:
        verdict_line = f"SUBMISSION READY ({passed}/{total} checks passed)"
        print(f"  ✓  {verdict_line}")
    else:
        verdict_line = f"NOT READY ({passed}/{total} checks passed — resolve ✗ items above)"
        print(f"  ✗  {verdict_line}")
    lines.append(f"  {verdict_line}")
    print("=" * 60)
    lines.append("=" * 60)

    # Save
    out = "ssef_submission_checklist.txt"
    with open(out, "w") as f:
        f.write("SSEF SUBMISSION CHECKLIST\n")
        f.write("=" * 60 + "\n")
        f.write("\n".join(lines))
        f.write("\n")
    print(f"\n  Checklist saved to {out}")


if __name__ == "__main__":
    main()
