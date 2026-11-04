# Panel

A panel is the unit of every game screen: one title, one meta line, one job.

- Structure: `section.fg-panel` > `div.fg-panel__head` (an `h2.fg-panel__title` and a `span.fg-meta`) > content.
- Plots (star map, charts, logs) sit inside `div.fg-panel__plot` on `surface-sunken`.
- Panels never nest and never carry shadows. Separate content inside a panel with `border-subtle` rules.
- The meta line holds context in data style: counts, units, tick of last update ("23 systems · 6 surveyed").
