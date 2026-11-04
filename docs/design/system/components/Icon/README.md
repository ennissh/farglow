# Icon

Game icons for resources, bodies, space, buildings, fleets, status, objectives and interface. One shared set for every civilization, so any player can read any map.

- Draw with `FarglowArt.icon(name, size)` from `lib/farglow-art.js`. It returns an inline SVG that strokes in `currentColor`, so set the colour on the parent (`--ink`, `--ink-muted`, `--accent` for yours, `--signal` for others).
- 24px grid, 1.5px stroke, round caps and joins, no fills except tiny dots.
- Sizes: 16px in dense tables, 20px default, 24px in panel headers. Never below 16px.
- Always pair an icon with a number or a label on game screens. An icon alone is a hint, not data.
- Static single-ink copies live in **assets/Icons** for other tools.
