SELECT l.line_ref,
       'commission rate ' || round(l.commission / l.premium, 4)
           || ' vs treaty rate ' || t.commission_rate AS message
FROM account_lines l
JOIN treaties t ON t.treaty_id = l.treaty_id
WHERE l.premium IS NOT NULL AND l.premium <> 0 AND l.commission IS NOT NULL
  AND abs(l.commission / l.premium - t.commission_rate) > %(rate_tolerance)s
