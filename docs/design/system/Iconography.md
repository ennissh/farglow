# Iconography and art

Farglow's art is drawn in code, not stored as pictures. One file, `lib/farglow-art.js`, draws every icon, civilization set, planet and star as inline SVG.

## Three kinds of art

| Kind | How many | Theme behaviour |
|---|---|---|
| **Icons** | 60, one shared set for everyone | Stroke in `currentColor`; follow the text colour |
| **Civilization sets** | 32: emblem, colour pair, banner, ship livery | Field colours work on both themes; outlines use tokens |
| **Bodies** | Unlimited: planets, stars, belts from a seed | Physical colours; same in both themes |

## Rules

- **Civ colour is identity; blue and orange are relation.** A civ's colour fills its emblem and territory. "You" (accent blue) and "others" (signal orange) are still shown by rings and badges.
- **Every icon on a game screen sits next to a number or label.**
- **No real-world symbols** in emblems: no flags, religious, political or hate symbols.
- **Planets are never stored.** Seed + type in, the same picture out, on every client.

## Logo

**F-Horizon** is the Farglow mark: the F's top stroke is a horizon arc, its crossbar a binary pair of suns rising. Files and rules are in **assets/Logo**. The other nine concepts stay on the Farglow Screens canvas (board 17) for reference. Run a trademark search before launch.
