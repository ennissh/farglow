// Render a .dc.html board as plain HTML for a quick screenshot check (no canvas runtime).
// usage: node preview.js board.dc.html out.png [light|dark] [width] [height]
const fs = require('fs');
const { chromium } = require('playwright');
(async () => {
  const [src, png, theme = 'light', w = '1440', h = '1000'] = process.argv.slice(2);
  let html = fs.readFileSync(src, 'utf8');
  const helmet = (html.match(/<helmet>([\s\S]*?)<\/helmet>/) || [, ''])[1];
  const css = fs.readFileSync(process.env.FG_CSS, 'utf8');
  html = html.replace(/<helmet>[\s\S]*?<\/helmet>/, '').replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<link rel="stylesheet" href="ds[^>]*>/, `<style>${css}</style>`)
    .replace('</head>', `${helmet}</head>`)
    .replace(/\{\{themeClass\}\}/g, theme === 'dark' ? 'fg-dark' : 'fg-light')
    .replace(/<\/?x-dc>/g, '');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
  await p.setContent(html, { waitUntil: 'networkidle' }).catch(() => {});
  await p.waitForTimeout(400);
  await p.screenshot({ path: png, fullPage: true });
  await b.close();
  console.log('shot', png);
})();
