# Button

Buttons commit an action: one primary per panel, secondary for alternatives, ghost for low-emphasis links, danger only for irreversible acts.

- Classes: `fg-btn` plus `fg-btn--primary`, `--secondary`, `--ghost` or `--danger`; add `fg-btn--sm` inside table rows and panel headers.
- Default height is `control-h` (44 px); compact is `control-h-sm` (32 px), desktop pointer use only.
- Labels are verbs that say what happens: "Confirm orders", "Queue for next tick", "Propose treaty". Never "OK" or "Submit".
- Danger buttons (declare war, abandon colony, begin transcendence) always open a confirmation step that restates the consequence.
- Use a real `<button type="button">` (or `<a class="fg-btn">` for navigation). Icon-only buttons need `aria-label`.
