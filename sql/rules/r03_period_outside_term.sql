SELECT l.line_ref,
       'period ' || l.period_start || ' to ' || l.period_end
           || ' outside treaty term ' || t.term_start || ' to ' || t.term_end AS message
FROM account_lines l
JOIN treaties t ON t.treaty_id = l.treaty_id
WHERE l.period_start < t.term_start OR l.period_end > t.term_end
