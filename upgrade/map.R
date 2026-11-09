library(ggplot2)
v <- read.csv("inputs/boundary_vertices.csv")
stopifnot(length(unique(v$towncode)) == 18, length(unique(v$towncode[v$group == "Nearby comparison"])) == 5)
labels <- data.frame(
  label = c("Tongluo", "Miaoli City", "Gongguan", "Sanyi", "Xihu", "Touwu"),
  lon = c(120.807, 120.803, 120.860, 120.775, 120.757, 120.877),
  lat = c(24.452, 24.558, 24.487, 24.393, 24.500, 24.560)
)
p <- ggplot(v, aes(lon, lat)) +
  geom_polygon(aes(group = towncode, subgroup = ring, fill = group),
               colour = "#ffffff", linewidth = .32, rule = "evenodd") +
  geom_text(data = labels, aes(label = label), size = 3, fontface = "bold", colour = "#142a3b") +
  scale_fill_manual(values = c("Tongluo" = "#70b7ad", "Nearby comparison" = "#f0c18f", "Other Miaoli" = "#e2e8ec"),
                    breaks = c("Tongluo", "Nearby comparison", "Other Miaoli")) +
  coord_fixed(ratio = 1 / cos(24.5 * pi / 180), expand = FALSE) +
  labs(title = "Tongluo and the five comparison towns", subtitle = "Administrative areas used in the property analysis",
       x = NULL, y = NULL, fill = NULL,
       caption = "Source: Taiwan MOI / NLSC township boundaries, TOWN_MOI_1140318.\nTownship groups only. The map shows neither transaction locations nor distance from P5.") +
  theme_void(base_size = 11) + theme(legend.position = "bottom",
    plot.title = element_text(face = "bold", margin = margin(b = 5)),
    plot.subtitle = element_text(margin = margin(b = 10)),
    plot.caption = element_text(hjust = 0, margin = margin(t = 7), size = 8),
    plot.margin = margin(11, 14, 11, 14))
ggsave("figures/study_geography.png", p, width = 7.2, height = 5.5, dpi = 205, bg = "white")
