# Farglow

The interface for Farglow, a Generative Distractions game: a grounded, scientifically realistic social 4X set in a real-scale Milky Way. The look is **clean scientific**: an instrument panel for a civilization, where the wonder comes from real data presented clearly rather than from decoration.

Desktop only. Light and dark themes are equal citizens: every screen, token and component must work in both.

## Principles

1. **The data is the delight.** Real star classes, light-years, tonnage and tick counts are the setting. Show them precisely and let them carry the mood. No decorative gradients, glows or textures.
2. **Dense, never cluttered.** Game screens are data-dense by design. Density comes from tight, well-aligned tables and panels on a strict grid, not from cramming. Every panel has one title, one meta line, one job.
3. **You are blue, others are orange.** `accent` always means *you* (your systems, fleets, actions). `signal` always means *others* or *needs your attention*. Never swap them, and never rely on colour alone: pair it with a shape (circle = yours, square = theirs) or a label.
4. **Five-minute friendly.** The most important decision on any screen sits top-left or in the primary button. Depth is one click away, never in the way.
5. **Borders, not shadows.** Panels are outlined with `border` on `surface`. Shadows (`shadow-popover`) are only for things that float.

## Voice and content

- Plain English a 13-year-old and a 60-year-old both understand. Science words are fine when they are the real word ("tidally locked", "K2 dwarf"); explain them once on hover.
- Always give units: `4.1 ly`, `1,200 t`, `6 ticks`, `86%`. Time in the game is **ticks**; show real time only as a hint ("next tick in 42 min").
- Numbers use thousands separators and the `data-*` styles (mono, tabular).
- Headlines in sentence case, no exclamation marks. News is written like a calm wire service: what happened, where, how old the news is.
- Never use names, terms or art from other games or shows. Farglow has its own lexicon: fold transit, the Reach tier, the Meridian Dispatch, Remnants.

## Colour

| Role | Token | Use |
| --- | --- | --- |
| Ground | `bg` | Behind the panel grid |
| Panels | `surface`, `border` | Every panel and card |
| Plots | `surface-sunken`, `border-subtle` | Star map, charts, logs |
| Text | `ink`, `ink-secondary`, `ink-muted` | Primary, body, meta |
| You | `accent`, `accent-soft`, `on-accent` | Your assets, primary buttons, selection, links |
| Others / attention | `signal`, `signal-soft`, `on-signal` | Other civs, incoming threats, pending decisions |
| Good news | `positive`, `positive-soft` | Gains, treaties in force |
| Destructive | `danger`, `danger-soft` | War, abandonment, errors (always labelled) |
| Stars | `star-k`, `star-m`, `star-hot` | Map glyph tints only, decorative |

All text tokens reach 4.5:1 on `surface` and `bg` in both themes. `border-strong` reaches 3:1 for control outlines.

## Typography

**Inter Tight** for everything you read; **IBM Plex Mono** for every number, timestamp, coordinate and category kicker. Both load from Google Fonts:

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
```

Use the type styles by class (`.heading-md`, `.body`, `.data-md`, `.kicker`). Numbers in tables are right-aligned and use `font-variant-numeric: tabular-nums`. The wordmark is lowercase **farglow** in `wordmark`.

## Layout

- **Compact density by default.** Farglow is a desktop strategy game: pack information tightly, on a strict grid.
- Target width 1280 to 1600 px. Header `header-h` (48 px). Page gutter and panel gap `space-3` (12 px).
- Game screens use a flexible main column plus a `sidebar-w` (380 px) detail column; three columns where the content earns it.
- Panels: `surface`, 1 px `border`, `radius-md`, padding `space-3`, inner gap `space-2`. Panel header = title (`heading-md`, 14 px) left, meta line (`data-sm`, 11 px) right.
- Table rows at least `row-h` (28 px). Controls are `control-h` (32 px); in-row and header buttons `control-h-sm` (24 px).
- Floors that keep it readable for players up to 60: running prose never below 13 px, nothing below 11 px, no click target below 24 px.

## Star map conventions

- Your systems: filled `accent` circle with an outer ring. Other civilizations: `signal` square. Unsurveyed stars: small `ink-muted` dots.
- Communications range: `accent-soft` fill with a dashed `accent` edge.
- Fleet vectors: solid line with arrowhead, labelled with tonnage and ETA in ticks.
- Grid: `border-subtle` lines every 2 ly, axis labels in `data-sm`.

## Iconography

Line icons, 1.5 px stroke, 16 or 20 px, inheriting `currentColor`. Recommended set: Lucide (pin an exact version). No emoji, no filled illustrative icons, no pictures of ships or aliens in the UI chrome.

## Themes and CSS

Load `tokens.css` and `components/bundle.css`, then set the theme on `<html>`:

```html
<html data-theme="light">
<script>
  // Respect the saved choice, else the OS preference.
  const saved = localStorage.getItem('fg-theme');
  const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = saved || (prefersDark ? 'dark' : 'light');
</script>
```

Components are plain CSS classes prefixed `fg-` (see Components). They read only tokens, so switching `data-theme` restyles everything. Never hard-code a hex value in a screen.

## Accessibility

- Text 4.5:1 in both themes; control borders, focus rings and map glyphs 3:1.
- Every interactive element shows a 2 px `focus` ring on `:focus-visible`.
- Meaning is never colour alone: shape, label or icon always accompanies `accent`, `signal`, `positive` and `danger`.
- Real `<button>`, `<a>`, `<label>`/`<input>` elements; icon-only buttons carry `aria-label`.

## Components

Button, Panel, DataTable, NavTabs, Badge, Field and Meter, each with guidelines and a live preview. All are CSS classes in `components/bundle.css`, usable from Flask/Jinja templates without a JavaScript framework.
