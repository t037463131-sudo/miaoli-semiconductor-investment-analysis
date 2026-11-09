SELECT township, contract_date, archive, segment, building_type, land_class,
       has_note, special, ntd_m2
FROM priced
WHERE ntd_m2 > 0
  AND segment IN ('Existing residential','Presale residential','Land only')
  AND contract_date >= '2023-01-01' AND contract_date < '2026-07-01'
ORDER BY market, serial;
