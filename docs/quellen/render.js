const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: 2, viewport: { width: 1300, height: 900 } });
  await p.goto('file://' + __dirname + '/bilder.html');
  await p.waitForTimeout(500);
  for (const id of ['hero','so-funktionierts','fahrplan','ram-ampel','modelle','tool-calling','kontext','wegweiser']) {
    await p.locator('#' + id).screenshot({ path: process.argv[2] + '/' + id + '.png', omitBackground: true });
  }
  await b.close();
})();
