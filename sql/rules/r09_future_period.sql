SELECT l.line_ref,
       'period ends ' || l.period_end || ' after submission date ' || s.submitted_on AS message
FROM account_lines l
JOIN submissions s ON s.submission_id = l.submission_id
WHERE l.period_end > s.submitted_on
