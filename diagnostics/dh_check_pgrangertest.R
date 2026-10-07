# Cross-check of prereg_analysis.dh_stats against plm::pgrangertest on a SIMULATED panel.
# 1. python3 diagnostics/dh_export_for_xtgcause.py 2 dh_check_panel.csv   (writes the CSV, prints the module's statistics)
# 2. Rscript diagnostics/dh_check_pgrangertest.R dh_check_panel.csv
# Verified 2026-10-07 with R 4.2.3 and plm 2.6.3: W-bar 4.389292, Z-bar 2.926273, Z-tilde 2.618628 in both.
suppressMessages(library(plm))
f <- commandArgs(trailingOnly = TRUE)[1]
pd <- pdata.frame(read.csv(f), index = c("id", "t"))
for (tt in c("Wbar", "Zbar", "Ztilde")) {
  r <- pgrangertest(y ~ x, data = pd, order = 2L, test = tt)
  cat(tt, "=", sprintf("%.6f", r$statistic), "\n")
}
