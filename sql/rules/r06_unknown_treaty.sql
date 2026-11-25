SELECT l.line_ref, 'treaty ' || l.treaty_id || ' not found' AS message
FROM account_lines l
WHERE l.treaty_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM treaties t WHERE t.treaty_id = l.treaty_id)
