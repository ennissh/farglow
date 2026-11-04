// Shared shell for Farglow Screens canvas boards (same helmet/theme pattern as boards 1-16).
const VARS_LIGHT = '--bg:#F3F4F1;--surface:#FFFFFF;--surface-sunken:#FBFBFA;--surface-raised:#EEF0EE;--border:#D5D9DE;--border-subtle:#E6E9EC;--border-strong:#8A929C;--ink:#141A22;--ink-secondary:#3A434E;--ink-muted:#56606C;--accent:#1D5BB8;--accent-hover:#174B98;--on-accent:#FFFFFF;--accent-soft:#E3ECF9;--signal:#B8460E;--signal-soft:#FBEADF;--positive:#1E7A4C;--positive-soft:#E2F3EA;--danger:#B42318;--danger-soft:#FBE4E2;--glow:#D2790F;--glow-2:#1D5BB8;--star-k:#D9822B;--star-m:#C2410C;--star-hot:#2563EB';
const VARS_DARK = '--bg:#0F1318;--surface:#161B22;--surface-sunken:#11161C;--surface-raised:#1E242D;--border:#2C333D;--border-subtle:#222831;--border-strong:#5A6472;--ink:#E6EAEF;--ink-secondary:#B9C1CB;--ink-muted:#8C96A3;--accent:#6EA2F0;--accent-hover:#8DB6F4;--on-accent:#0F1318;--accent-soft:#1C2B45;--signal:#F0915A;--signal-soft:#3A2418;--positive:#5CC48F;--positive-soft:#15301F;--danger:#F27D74;--danger-soft:#3A1A18;--glow:#F5B547;--glow-2:#8DB6F4;--star-k:#F2A65A;--star-m:#F08A5D;--star-hot:#9EC1FF';

function board({ title, body, height = 1000, extraCss = '', script = '' }) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Farglow — ${title}</title>
<script src="./support.js"></script>
<link rel="stylesheet" href="ds/farglow/components/bundle.css">
</head>
<body>
<x-dc>
<helmet>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap">
<style>
body{margin:0}
a{color:var(--accent)}a:hover{color:var(--accent-hover)}
.fg-root{--font-sans:"Inter Tight","Inter",system-ui,sans-serif;--font-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--radius-sm:3px;--radius-md:4px;--radius-lg:6px;--control-h:32px;--control-h-sm:24px;--row-h:28px;--focus:var(--accent)}
.fg-light{${VARS_LIGHT}}
.fg-dark{${VARS_DARK}}
${extraCss}
</style>
</helmet>
<div class="fg-app fg-root {{themeClass}}" style="min-height: ${height}px; box-sizing: border-box; background: var(--bg); color: var(--ink)">
${body}
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{"theme":{"editor":"enum","options":["light","dark"],"default":"light"},"$preview":{"width":1440,"height":${height}}}'>
class Component extends DCLogic {
${script || 'renderVals() { return { themeClass: (this.props.theme ?? \'light\') === \'dark\' ? \'fg-dark\' : \'fg-light\' }; }'}
}
</script>
</body>
</html>
`;
}
module.exports = { board, VARS_LIGHT, VARS_DARK };
