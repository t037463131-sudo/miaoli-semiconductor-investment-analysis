-- The two stages keep enrollment and price calculation auditable.
CREATE VIEW classified AS
SELECT *,
  CASE WHEN township = 'Tongluo' THEN 'Tongluo'
       WHEN township IN ('Miaoli City','Gongguan','Sanyi','Xihu','Touwu') THEN 'Nearby pool'
       ELSE 'Other Miaoli' END AS geography,
  CASE WHEN target = '土地' AND land_area > 0 THEN 'Land only'
       WHEN target IN ('房地(土地+建物)','房地(土地+建物)+車位')
            AND purpose IN ('住家用','住宅用') AND building_count = 1
            AND building_area > parking_area
            AND (parking_count = 0 OR (parking_area > 0 AND parking_price > 0))
         THEN CASE WHEN market = 'a' THEN 'Existing residential' ELSE 'Presale residential' END
  END AS segment,
  CASE WHEN urban IN ('農','都市：其他:農業區') OR land_use = '農牧用地' THEN 'Agriculture'
       WHEN urban IN ('工','都市：其他:工業區') OR land_use = '丁種建築用地' THEN 'Industrial proxy'
       WHEN urban = '住' OR urban LIKE '%住宅區%' OR land_use IN ('甲種建築用地','乙種建築用地','丙種建築用地')
         THEN 'Residential/building proxy' ELSE 'Other/unspecified' END AS land_class
FROM deals;

CREATE VIEW priced AS
SELECT *,
  CASE WHEN segment = 'Land only' THEN price / land_area
       WHEN segment IS NOT NULL THEN (price - parking_price) / (building_area - parking_area)
  END AS ntd_m2
FROM classified;

CREATE VIEW sample AS
SELECT * FROM priced WHERE ntd_m2 > 0 AND special = 0;
