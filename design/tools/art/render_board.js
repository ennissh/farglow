// Static renderer for .dc.html boards: runs the board's DCLogic renderVals() and fills the template
// (sc-for, sc-if, {{…}}), then screenshots it. Good enough for PNG exports of the mockups.
// usage: FG_CSS=bundle.css node render_board.js board.dc.html out.png [light|dark] [w] [h]
const fs = require('fs');
const { chromium } = require('playwright');

function getVals(html, theme) {
  const m = html.match(/<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/);
  if (!m) return { themeClass: theme === 'dark' ? 'fg-dark' : 'fg-light' };
  class DCLogic { constructor(props) { this.props = props || {}; this.state = {}; } setState(s) { Object.assign(this.state, s); } }
  // eslint-disable-next-line no-new-func
  const Component = new Function('DCLogic', `${m[1]}; return Component;`)(DCLogic);
  const c = new Component({ theme });
  return c.renderVals();
}
const get = (scope, path) => path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), scope);
const str = (v) => (typeof v === 'function' || v == null ? '' : String(v));
function fill(tpl, scope) {
  // sc-for (innermost first)
  let guard = 0;
  const forRe = /<sc-for list="\{\{([^}]+)\}\}" as="(\w+)"[^>]*>((?:(?!<sc-for)[\s\S])*?)<\/sc-for>/;
  while (forRe.test(tpl) && guard++ < 500) {
    tpl = tpl.replace(forRe, (_, path, as, inner) => (get(scope, path.trim()) || []).map((item) => fill(inner, { ...scope, [as]: item })).join(''));
  }
  const ifRe = /<sc-if value="\{\{([^}]+)\}\}"[^>]*>((?:(?!<sc-if)[\s\S])*?)<\/sc-if>/;
  guard = 0;
  while (ifRe.test(tpl) && guard++ < 500) tpl = tpl.replace(ifRe, (_, path, inner) => (get(scope, path.trim()) ? inner : ''));
  return tpl.replace(/\{\{([^}]+)\}\}/g, (_, p) => str(get(scope, p.trim())));
}
(async () => {
  const [src, png, theme = 'light', w = '1440', h = '1000'] = process.argv.slice(2);
  let html = fs.readFileSync(src, 'utf8');
  const vals = getVals(html, theme);
  const helmet = (html.match(/<helmet>([\s\S]*?)<\/helmet>/) || [, ''])[1];
  const body = (html.match(/<x-dc>([\s\S]*?)<\/x-dc>/) || [, ''])[1].replace(/<helmet>[\s\S]*?<\/helmet>/, '');
  const css = fs.readFileSync(process.env.FG_CSS, 'utf8');
  const page = `<!doctype html><html lang="en"><head><meta charset="utf-8"><style>${css}</style>${helmet}</head><body>${fill(body, vals)}</body></html>`;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 2 });
  await p.setContent(page, { waitUntil: 'networkidle' }).catch(() => {});
  await p.waitForTimeout(500);
  await p.screenshot({ path: png, fullPage: true });
  await b.close();
})();
