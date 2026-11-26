// node build.js : génère ebook.pdf et slides.pdf depuis les HTML
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  for (const [src, out, opts] of [
    ['ebook.html', 'ebook.pdf', { format: 'A4', displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#888"><span class="pageNumber"></span></div>',
      margin: { top: '22mm', bottom: '22mm', left: '20mm', right: '20mm' } }],
    ['slides.html', 'slides.pdf', { width: '1280px', height: '720px', margin: { top: 0, bottom: 0, left: 0, right: 0 } }],
  ]) {
    try { await p.goto('file://' + path.resolve(__dirname, src)); } catch (e) { console.log('skip', src); continue; }
    await p.pdf({ path: path.resolve(__dirname, out), printBackground: true, preferCSSPageSize: false, ...opts });
    console.log('ok', out);
  }
  await b.close();
})();
