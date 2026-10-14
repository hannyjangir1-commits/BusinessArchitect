const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACTS_DIR = path.resolve(__dirname, '..', 'test-artifacts');
const APP_URL = 'http://127.0.0.1:5173';

if (!fs.existsSync(ARTIFACTS_DIR)) {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

(async () => {
  console.log('====================================================');
  console.log('AI BUSINESS ARCHITECT — REAL CHROME E2E VERIFICATION');
  console.log('====================================================\n');

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1400,900']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  const consoleLogs = [];
  const networkErrors = [];

  page.on('console', msg => {
    const text = msg.text();
    consoleLogs.push(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error') {
      console.error('BROWSER CONSOLE ERROR:', text);
    }
  });

  page.on('requestfailed', request => {
    networkErrors.push(`${request.method()} ${request.url()} - ${request.failure()?.errorText}`);
    console.warn('NETWORK REQUEST FAILED:', request.method(), request.url(), request.failure()?.errorText);
  });

  const testResults = [];

  async function takeScreenshot(name) {
    const filePath = path.join(ARTIFACTS_DIR, name);
    await page.screenshot({ path: filePath, fullPage: false });
    console.log(`[SCREENSHOT] Saved: ${name}`);
    return filePath;
  }

  try {
    // ----------------------------------------------------
    // WORKFLOW 1: Landing Page & Registration Flow
    // ----------------------------------------------------
    console.log('\n--- WORKFLOW 1: Landing Page & User Registration ---');
    await page.goto(APP_URL, { waitUntil: 'networkidle0' });
    await takeScreenshot('01_landing_page.png');

    // Click "Get Started Free"
    const getStartedBtn = await page.waitForSelector('button.btn-primary');
    await getStartedBtn.click();
    await sleep(500);

    const testUser = `founder_chrome_${Date.now().toString().slice(-6)}`;
    const testEmail = `${testUser}@venturetest.internal`;
    const testPassword = 'Password123!';

    console.log(`Registering dedicated local user: ${testUser}`);

    // Fill registration form
    await page.waitForSelector('input[placeholder="e.g. founder_alice"]');
    await page.type('input[placeholder="e.g. founder_alice"]', testUser);
    await page.type('input[placeholder="name@venture.com"]', testEmail);
    await page.type('input[placeholder="At least 8 characters with letter and number"]', testPassword);
    await page.type('input[placeholder="Re-enter password"]', testPassword);
    
    // Check terms
    await page.click('#terms');
    await sleep(200);

    await takeScreenshot('02_registration_modal.png');

    // Submit registration
    await page.click('button[type="submit"]');
    await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 8000 }).catch(() => {});
    await sleep(1500);

    const dashboardTitle = await page.$eval('h1', el => el.textContent).catch(() => '');
    console.log('Current Dashboard Header:', dashboardTitle);
    await takeScreenshot('03_dashboard_view.png');

    testResults.push({
      workflow: '1. Landing Page, Registration & Dashboard',
      passed: dashboardTitle.includes('Venture Architecture Portfolio'),
      evidence: '01_landing_page.png, 02_registration_modal.png, 03_dashboard_view.png'
    });

  } catch (err) {
    console.error('Test execution error:', err);
  } finally {
    await browser.close();
    console.log('\nTest batch completed.');
  }
})();
