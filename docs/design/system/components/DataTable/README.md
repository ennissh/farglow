# DataTable

Dense, aligned tables are the backbone of Farglow's data-rich screens.

- `table.fg-table`; numeric cells get `class="num"` (right-aligned, mono, tabular figures).
- A secondary line inside a cell goes in `span.sub` (e.g. body type under a planet name).
- Rows are at least `row-h` (36 px). Hover uses `surface-raised`; the selected row sets `aria-selected="true"` and turns `accent-soft`.
- Status lives in a Badge, never in coloured text alone.
- Show an em dash for "none" so empty cells read as data, not as missing.
