SELECT line_ref, 'negative premium ' || premium || ' without reversal flag' AS message
FROM account_lines
WHERE premium < 0 AND NOT is_reversal
