SELECT line_ref,
       'balance ' || balance || ' but premium - commission - claims = '
           || (premium - commission - claims_paid) AS message
FROM account_lines
WHERE premium IS NOT NULL AND commission IS NOT NULL
  AND claims_paid IS NOT NULL AND balance IS NOT NULL
  AND abs(balance - (premium - commission - claims_paid)) > %(tolerance)s
