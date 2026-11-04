# NavTabs

The four main game views live in one segmented tab bar in the header: Galaxy, Governor, Dispatch, Diplomacy.

- `nav.fg-tabs` holding `a.fg-tab` links; the current view sets `aria-current="page"`.
- A pending count (unread news, open treaty offers) uses `span.fg-tab__count` in signal colours.
- Keep the order fixed so muscle memory works; never add more than six tabs.
