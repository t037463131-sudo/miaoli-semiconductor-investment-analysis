# Run from the upgrade directory. Requires R >= 4.2 and ggplot2 for figures.
dir.create("results", showWarnings = FALSE)
dir.create("figures", showWarnings = FALSE)
deals <- read.csv("inputs/r_price_sample.csv", stringsAsFactors = FALSE)
original <- read.csv("inputs/original_market_statistics.csv", fileEncoding = "UTF-8-BOM",
                     stringsAsFactors = FALSE)
towns <- c("Miaoli City", "Gongguan", "Sanyi", "Xihu", "Touwu")
segments <- c("Existing residential", "Presale residential", "Land only")
deals$year <- as.integer(substr(deals$contract_date, 1, 4))
deals$month <- as.integer(substr(deals$contract_date, 6, 7))
deals$home_type <- ifelse(grepl("^透天厝", deals$building_type), "Townhouse",
                          ifelse(grepl("^(公寓|華廈|住宅大樓)", deals$building_type),
                                 "Apartment/condo", "Other"))
deals$matched <- as.integer(substr(deals$archive, 1, 3)) * 10 +
  as.integer(substr(deals$archive, 5, 5)) <= (deals$year - 1911) * 10 + 3

measures <- function(d, from, to) {
  a <- d$ntd_m2[d$year == from]
  b <- d$ntd_m2[d$year == to]
  med_a <- if (length(a)) median(a) else NA_real_
  med_b <- if (length(b)) median(b) else NA_real_
  data.frame(n_before = length(a), n_after = length(b), median_before = med_a,
             median_after = med_b, change_pct = 100 * (med_b / med_a - 1))
}
output <- function(x, name) write.csv(x, file.path("results", paste0(name, ".csv")), row.names = FALSE, na = "")
collect <- function(grid, compute) do.call(rbind, lapply(seq_len(nrow(grid)), function(i) {
  cbind(grid[i, , drop = FALSE], compute(grid[i, , drop = FALSE]))
}))

q2 <- subset(deals, month %in% 4:6)
rules <- list(main = function(d) d$special == 0,
              all_priced = function(d) rep(TRUE, nrow(d)),
              no_remarks = function(d) d$special == 0 & d$has_note == 0,
              matched_archive = function(d) d$special == 0 & d$matched)
groups <- list(Tongluo = function(d) d$township == "Tongluo",
               "Nearby pool" = function(d) d$township %in% towns,
               "County excluding Tongluo" = function(d) d$township != "Tongluo")
grid <- expand.grid(geography = names(groups), segment = segments, rule = names(rules),
                    stringsAsFactors = FALSE)
check <- collect(grid, function(r) {
  d <- q2[q2$segment == r$segment & groups[[r$geography]](q2) & rules[[r$rule]](q2), ]
  measures(d, 2025, 2026)
})
for (i in seq_len(nrow(check))) {
  r <- check[i, ]
  old <- original[original$geography == r$geography & original$segment == r$segment &
                  original$filter == r$rule & original$stratum == "All" &
                  original$period %in% c("2025 Apr-Jun", "2026 Apr-Jun"), ]
  old <- old[order(old$period), ]
  stopifnot(nrow(old) == 2, all(old$n == c(r$n_before, r$n_after)),
            all(abs(old$median_ntd_m2 - c(r$median_before, r$median_after)) <= 0.00501))
}
output(check, "r_crosscheck")

main <- subset(q2, special == 0)
loo <- collect(expand.grid(segment = segments, excluded = c("None", towns),
                           stringsAsFactors = FALSE), function(r) {
  comp <- subset(main, segment == r$segment & township %in% setdiff(towns, r$excluded))
  exposed <- subset(main, segment == r$segment & township == "Tongluo")
  v <- measures(comp, 2025, 2026)
  v$tongluo_change_pct <- measures(exposed, 2025, 2026)$change_pct
  v$gap_pp <- v$tongluo_change_pct - v$change_pct
  v
})
output(loo, "leave_one_town_out")

pre <- collect(expand.grid(segment = segments, start = 2023:2025,
                           stringsAsFactors = FALSE), function(r) {
  t <- measures(subset(main, segment == r$segment & township == "Tongluo"), r$start, r$start + 1)
  c <- measures(subset(main, segment == r$segment & township %in% towns), r$start, r$start + 1)
  data.frame(tongluo_n_before = t$n_before, tongluo_n_after = t$n_after,
             tongluo_change_pct = t$change_pct, nearby_n_before = c$n_before,
             nearby_n_after = c$n_after, nearby_change_pct = c$change_pct,
             gap_pp = t$change_pct - c$change_pct)
})
output(pre, "same_quarter_history")

mix <- collect(expand.grid(geography = c("Tongluo", "Nearby pool"),
                           rule = c("main", "all_priced", "matched_archive"),
                           home_type = c("Townhouse", "Apartment/condo", "Other"),
                           stringsAsFactors = FALSE), function(r) {
  eligible <- q2[q2$segment == "Existing residential" & groups[[r$geography]](q2) &
                 rules[[r$rule]](q2), ]
  v <- measures(subset(eligible, home_type == r$home_type), 2025, 2026)
  v$share_before_pct <- 100 * v$n_before / sum(eligible$year == 2025)
  v$share_after_pct <- 100 * v$n_after / sum(eligible$year == 2026)
  v
})
output(mix, "completed_home_mix")
writeLines(capture.output(sessionInfo()), "results/r_session.txt")

if (requireNamespace("ggplot2", quietly = TRUE)) {
  library(ggplot2)
  writeLines(paste("ggplot2", packageVersion("ggplot2")), "results/figure_engine.txt")
  labels <- c("Existing residential" = "Completed homes", "Presale residential" = "Presales",
              "Land only" = "Land only")
  l <- subset(loo, excluded != "None")
  l$segment <- factor(labels[l$segment], levels = unname(labels))
  l$excluded <- factor(l$excluded, levels = rev(towns))
  p <- ggplot(l, aes(gap_pp, excluded)) +
    geom_vline(xintercept = 0, linewidth = .35, colour = "#7990a2") +
    geom_point(colour = "#086d71", size = 3) +
    facet_wrap(~segment, nrow = 1, scales = "free_x") +
    labs(title = "Does the choice of nearby town change the result?",
         subtitle = "2025 to 2026 Q2 median changes, with one nearby town removed at a time",
         x = "Tongluo minus comparison group (percentage points)", y = "Town omitted",
         caption = "Positive values mean Tongluo's median grew faster or fell less. Descriptive comparisons.") +
    theme_minimal(base_size = 11) + theme(panel.grid.minor = element_blank(),
      plot.title = element_text(face = "bold"), strip.text = element_text(face = "bold"))
  ggsave("figures/comparator_check.png", p, width = 9.4, height = 4.1, dpi = 200, bg = "white")
} else {
  writeLines("Base R fallback (ggplot2 unavailable)", "results/figure_engine.txt")
  png("figures/comparator_check.png", width = 1880, height = 820, res = 200)
  par(mfrow = c(1,3), mar = c(5,7,4,1), oma = c(0,0,2,0))
  for (s in segments) {
    v <- subset(loo, segment == s & excluded != "None")
    plot(v$gap_pp, seq_len(nrow(v)), yaxt = "n", pch = 19, col = "#086d71",
         xlim = range(c(v$gap_pp, 0)), xlab = "Tongluo minus nearby (pp)", ylab = "", main = s)
    axis(2, at = seq_len(nrow(v)), labels = v$excluded, las = 1, cex.axis = .75)
    abline(v = 0, col = "#7990a2")
  }
  mtext("2025 to 2026 Q2 comparison with one nearby town omitted", outer = TRUE, line = .4)
  dev.off()
}
