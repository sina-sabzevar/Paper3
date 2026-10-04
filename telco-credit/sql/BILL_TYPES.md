# The 24 bill types

Source: `info.xlsx`, the bill-type dimension, `src_sys_id` 1999319,
loaded 2026-10-01.

`cust_bil_typ_id` is a **VARCHAR** holding a 48-character surrogate key, so a
quoted literal matches it exactly and the key can be used directly. Two
cautions, both from string comparison being exact:

- The end-of-cycle value on record matches the dimension's `monthly Bill` row.
  The mid-cycle value supplied earlier does **not** — same leading digits as
  `Hot Bill` but 47 characters and an order of magnitude small, so a character
  was lost in transit. As a literal it would match nothing, silently.
- Take the literals from a `GROUP BY` on the fact table (`D2` in
  `31_bill_type_resolved.sql`), never from a spreadsheet: a spreadsheet parses
  the text as a number for display, and float64 keeps about 17 significant
  digits.

Filtering on `unq_id_in_src_sys` through a dimension join avoids the long
literal altogether and is the safer form where the join is acceptable.

| code | `cust_bil_typ` | bears on a credit obligation? |
|---|---|---|
| `5` | **monthly Bill** | **yes — this is end-of-cycle** |
| `7` | **Hot Bill** | **yes — this is mid-cycle** |
| `L` | Late payment fee Bill | money owed |
| `R` | Surcharge Bill | money owed |
| `T` | Tax Bill | money owed |
| `2` | Installation Bill | money owed |
| `3` | Repair Bill | money owed |
| `4` | Phone and Accessories Bill | money owed |
| `1` | Contract Based Bill | money owed |
| `S` | Service Bill in advance | prepaid, not arrears |
| `F` | forfeit | |
| `M` | Deposit | money held, not owed |
| `N` | Deposit Bill | money held |
| `8` | Requested Deposit | money held |
| `9` | Requested Advance Payment | money held |
| `V` | Advance Payment Bill | money held |
| `A` | Upfront Advance Payment | money held |
| `B` | Overpayment Bill | credit balance |
| `C` | Adjustment Bill | either sign |
| `6` | Storno | a reversal |
| `D` | From transfer | |
| `E` | Post paid topup added | |
| `Z` | Other Bill | |
| `-1` | Unknown | |

The right-hand column is a reading of the names, not a measurement. `D4` in
`31_bill_type_resolved.sql` ranks every type by amount so the question becomes
arithmetic rather than interpretation.

## What this corrects

`11_dcb_extract_v3.sql` and `25_scoreset.sql` filter `cust_bil_typ_id = 2` for
end-of-cycle and `= 3` for mid-cycle. **No dimension row has a surrogate id of
2 or 3.** Register item G — `mc_billed_6m` entirely NULL — has its cause: the
filter matched zero rows, and `SUM(x) FILTER` over zero rows returns NULL.

Note the trap in the codes themselves: `unq_id_in_src_sys` **does** have `'2'`
and `'3'`, and they are Installation Bill and Repair Bill. So a filter written
against the short code would also have been wrong, just wrong differently —
it would have measured installation and repair charges and called them the
monthly bill.

`D2` must confirm which encoding the fact table uses before any of this
replaces the current filter.
