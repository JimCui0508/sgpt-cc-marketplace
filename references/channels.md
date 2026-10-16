# C1 / C2 / C3 + full SGPT map

Source: `results/CHANNEL_RECOVERY.md` (observational n=41).

| Channel | How | Recoverable |
|---------|-----|-------------|
| C1 stream | default stream markers | often none (0/41) |
| C2 +post | bare `/goal` → Goal active / No goal set | retain; Met\|Imp ambiguous (20/41) |
| C3 +debug | Stop-hook `ok` / `impossible` | Met, Impossible, retain (41/41) |

## Full protocol pieces

| Piece | Plugin entry | Wraps |
|-------|--------------|-------|
| Independent clauses | `sgpt clause` / `/sgpt-clause` | `independent_evid_full_ok` |
| Receipts | `sgpt receipts` / `/sgpt-receipts` | `sgpt_receipts` |
| Taxonomy harvest | `sgpt taxonomy` | `sgpt_taxonomy` |
| Intervention A | `sgpt intervene` / `/sgpt-intervene` | `goal_interp_product_a` / `goal_interp_intervene` |

Honest incremental value: protocol scoring the same exit under C1/C2/C3 + external clauses — not a new sensor beyond product debug+post.
