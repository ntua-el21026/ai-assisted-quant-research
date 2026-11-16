# Original synthetic corporate-action fixture

This fixture is entirely artificial and dedicated under CC0-1.0. `SYN` and
`synthetic:001` are fictional identifiers. Prices, quantities, action knowledge,
acquisition receipts and dates are constructed for software verification; they
are not Alpaca observations or historical research evidence.

The six declared weekdays cross New York's March 2024 daylight-saving boundary.
This is an explicit synthetic calendar, not a qualified exchange holiday calendar.
Raw prices are 400, 100, 99, 9.9, 10 and 11. Splits are 4:1 on March 11 and 10:1
on March 13. A one-dollar dividend goes ex March 12 and pays March 14. The later
split must not change its already-fixed dollar entitlement.

Acquisition page hashes identify the original synthetic receipt strings
`original synthetic receipt synthetic-bars` and
`original synthetic receipt synthetic-actions`; they do not claim provider responses.
Query hashes identify the declared artificial request metadata. Bar/action file
sizes and hashes are verified against the actual committed JSON files.

With 1000 initial cash, the independent terminal expectations are price return
1100, cash total return 1110 and payment-open reinvested total return 1111.
See [R4-A contracts](../../../docs/research/R4A_IMPLEMENTATION.md) for assumptions.
