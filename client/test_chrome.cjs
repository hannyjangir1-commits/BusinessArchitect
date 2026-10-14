const puppeteer = require('puppeteer-core');
const path = require('path');

(async () => {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  console.log(`Connecting to Chrome at ${chromePath}...`);
  
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,800']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.error('PAGE ERROR:', err.toString()));

  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle0' });
  const title = await page.title();
  console.log('Page Title:', title);

  const screenshotPath = path.resolve(__dirname, '..', 'test-artifacts', '01_landing_page.png');
  await page.screenshot({ path: screenshotPath });
  console.log('Screenshot saved to:', screenshotPath);

  await browser.close();
  console.log('Browser test completed successfully.');
})();
