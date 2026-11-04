# Meter

Meters show progress toward a known total: research progress, fleet readiness, transcendence, budget allocation.

- `div.fg-meter` > `div.fg-meter__row` (label and `span.fg-meter__value`) > `div.fg-meter__track` > `div.fg-meter__fill` with an inline `width`.
- Fill is `accent` for your own progress, `--signal` for something that needs attention (low readiness), `--positive` for completion.
- Always print the number; the bar is a glance aid, not the data.
