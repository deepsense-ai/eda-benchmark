# deepsense/store-audit

The agent reconstructs a store's July 2023 revenue after a month-long POS
outage, using `warehouse_dispatches.csv`, `product_catalog.csv`, and
`temperature_logs.csv` (see [instruction.md](instruction.md)). Getting the
exact figure requires several cleaning steps and two hidden cruxes:
duplicated dispatch rows, comma-decimal prices and temperatures,
inconsistently cased zone names, one dispatch whose `product_id` is actually
an EAN code, and a refrigerator failure night whose spoiled dispatch must be
excluded (detected by joining each dispatch to the latest zone temperature
and comparing against the product's safe threshold). The answer is a single
integer (PLN).

Crux 1 — EAN in product_id
One dispatch row has product_id = "5901234567891" — a 13-digit string, visually unlike
the 8-character alphanumeric catalog IDs. A left join reveals one unmatched row; 
looking it up by ean_code recovers the real product (PLN 250 × 18 units = +4,500 PLN).

Crux 2 — Disposal event, night of 17→18 July 
Eight rows at 03:17 are a write-off, not a sale. Multiple signals converge: 
only nighttime dispatch of the month, both Frozen and Meat zones far above safe temperature
limits at that moment, all products from exactly those two zones, 8 items logged at the 
same second with quantities above normal range. 
Dispatches later that day (temperatures back to normal) count as sales.
