# Field

Fields collect player input: account details, civilization name and backstory, policy settings.

- `div.fg-field` > `label.fg-label` (with `for`) > `input.fg-input`, `select.fg-select` or `textarea.fg-textarea` > optional `p.fg-help`.
- Errors set `aria-invalid="true"` on the control and use `p.fg-help.fg-help--error` with a sentence that says how to fix it.
- Inputs are `control-h` (44 px) tall with a `border-strong` outline (3:1 in both themes).
