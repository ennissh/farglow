# Emblem

A civilization set is what a player adopts at sign-up: an **emblem** (charge in a frame), a **colour pair** (field + trim), a **banner pattern** and a **ship livery**. 32 sets ship with the game.

- Draw with `FarglowArt.emblem(id, size)`, `banner(id, size)` and `livery(id, size)`.
- Every field colour is solved to the same brightness (relative luminance about 0.16), so one value reads at least 3.7:1 against both the light and dark backgrounds. That is why emblems need no separate dark versions; only the outline and the hull grey follow the theme (`--border-strong`, `--hull`).
- Field hues near the UI accent blue and signal orange are left out on purpose. **Civ colour is identity; blue and orange are relation.** On the map, a civ's territory uses its colour, and "you" vs "others" is still shown by the accent ring or the signal badge, never by the civ colour alone.
- Sizes: 16px map marker and table rows, 24px lists, 52-64px panels and banners.
- Motifs were screened to avoid national flags, religious, political and hate symbols (no crescents, crosses, six-point stars, swastika-like rotations, eagles, hammers, double lightning). Any new set must pass the same screen.
- Players pick from the 32 at sign-up; two civs on one server can't hold the same set.
