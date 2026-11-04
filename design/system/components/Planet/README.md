# Planet

Planets, stars and asteroid belts are drawn procedurally, never stored as images. The galaxy has billions of bodies; each is drawn from its seed and type, so the same seed always draws the same world and the server stores nothing.

- `FarglowArt.planet(seed, type, size)`: type is one of verdant, ocean, super_earth, rocky, gas_giant, ice. Use the body's permanent id as the seed.
- `FarglowArt.star(class, size, {companion})`: class O, B, A, F, G, K or M; companion draws a binary partner.
- `FarglowArt.belt(seed, size)`.
- Flat vector style to match the clean scientific look: base colour, features (continents, bands, craters, cracks), clouds, then one flat terminator shadow from the upper left.
- Planet and star colours are physical, not themed; they read on both backgrounds. Lines around them use theme tokens.
- On game screens, buildings, population and garrisons are placed around a planet as icon chips (see the System view board), MOO2-style.
