SELECT l.line_ref,
       'currency ' || l.currency || ' but treaty currency is ' || t.currency AS message
FROM account_lines l
JOIN treaties t ON t.treaty_id = l.treaty_id
WHERE l.currency IS NOT NULL AND l.currency <> t.currency
