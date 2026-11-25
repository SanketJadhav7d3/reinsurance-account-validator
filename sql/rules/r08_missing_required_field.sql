SELECT line_ref,
       'missing: ' || concat_ws(', ',
           CASE WHEN treaty_id IS NULL THEN 'treaty_id' END,
           CASE WHEN period_start IS NULL THEN 'period_start' END,
           CASE WHEN period_end IS NULL THEN 'period_end' END,
           CASE WHEN currency IS NULL THEN 'currency' END,
           CASE WHEN premium IS NULL THEN 'premium' END,
           CASE WHEN commission IS NULL THEN 'commission' END,
           CASE WHEN claims_paid IS NULL THEN 'claims_paid' END,
           CASE WHEN balance IS NULL THEN 'balance' END) AS message
FROM account_lines
WHERE treaty_id IS NULL OR period_start IS NULL OR period_end IS NULL OR currency IS NULL
   OR premium IS NULL OR commission IS NULL OR claims_paid IS NULL OR balance IS NULL
