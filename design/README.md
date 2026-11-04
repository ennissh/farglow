# Farglow design pack

Everything designed for Farglow up to 3 Nov 2026: brand, design system, art library, screen mockups, specs, game configs and the tools that produced them. Use it to seed the repository: `config/`, `tools/` and `docs/` map straight onto the repo layout in `README.md`.

| Folder | What's inside |
|---|---|
| `brand/logo/` | **F-Horizon**, the chosen mark: light and dark marks, wordmark lockups, a self-switching `favicon.svg`, usage rules |
| `brand/logo-concepts/` | All 10 logo concepts as one sheet, plus `logos.js` (the source of every concept) |
| `design-system/` | Farglow Design System: `tokens.json` (colours for both themes, type, spacing, 16 civ colours, hull, brand glow), `components/bundle.css` (the `fg-` classes), a README and preview for each component, `Iconography.md`, `lib/farglow-art.js`, and `assets/` (60 icons and 32 emblems as SVG, the logo) |
| `mockups/png/` | 19 screens rendered at 2×, plus dark versions of Galaxy, Governor and System view |
| `mockups/source/` | The editable `.dc.html` boards and `canvas.json` (Claude design-canvas format) |
| `explorations/` | The four original visual directions; "Clean scientific" was chosen |
| `specs/` | Advisor spec, decision log (3 Nov 2026), branded tech-tree PDF |
| `config/` | Engine data for the PoC: `tech_tree`, `balance`, `objectives` (Charters, Triumphs, Galactic Events), `moderation`, `galaxy` |
| `tools/` | `sim.py` (economy simulator), `techtree/build.py` (YAML → PDF), `art/` (art library and board builders, static renderer) |

## Screens (`mockups/png`)

| # | Screen | # | Screen |
|---|---|---|---|
| 01 | Sign in / new player | 11 | Colony management |
| 02 | Galaxy | 12 | Fleet orders |
| 03 | Governor | 13 | Settings |
| 04 | Dispatch (in game) | 14 | Self-host setup wizard |
| 05 | Diplomacy | 15 | Host admin · overview |
| 06 | Research | 16 | Guilds |
| 07 | Meet your advisor | 17 | Logo concepts |
| 08 | First Light + advisor drawer | 18 | System view (MOO2-style) |
| 09 | Morning Dispatch email | 19 | Host admin · operations |
| 10 | AI activity log | | |

## Using the files

- **Art in the game:** load `design-system/lib/farglow-art.js`, then call `FarglowArt.icon('minerals')`, `FarglowArt.emblem('beacon')`, `FarglowArt.planet(seed, 'verdant')` or `FarglowArt.star('G')`. Each returns inline SVG, so icons follow the text colour and theme.
- **Rebuild the tech-tree PDF:** `python3 tools/techtree/build.py config/tech_tree.poc.yaml tree.html`, then print `tree.html` to PDF with headless Chrome. The fonts come from the npm Fontsource packages.
- **Run the economy simulator:** `python3 tools/sim.py config/balance.poc.yaml config/tech_tree.poc.yaml 2400`. Set `SIM_TRACE=out.csv` for a per-tick trace.
- **Re-render a mockup to PNG:** `FG_CSS=design-system/components/bundle.css node tools/art/render_board.js mockups/source/Galaxy.dc.html galaxy.png light`. This needs Node and Playwright.
- **Component previews** (`design-system/components/*/preview.html`) are meant to be viewed inside the Design System page, which supplies `tokens.css`. Opened on their own they have no theme colours.

## Status and licence

Every config file is **PROPOSED v1** unless marked DECIDED. Fonts (Inter Tight, IBM Plex Mono) are loaded from Google Fonts or Fontsource under the SIL Open Font License 1.1 and are not bundled here. © 2026 Citus Technologies, LLC. Covered by the repository's `LICENSE.md` once committed. The Farglow name and logos are trademarks and are not licensed.
