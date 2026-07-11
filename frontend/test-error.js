const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('BROWSER_LOG:', msg.text()));
  page.on('pageerror', error => console.log('BROWSER_ERROR:', error.message));
  
  await page.goto('http://localhost:3000/login');
  
  await page.type('input[type="email"]', 'shehreyar@gmail.com');
  await page.type('input[type="password"]', 'password123');
  await page.click('button[type="submit"]');
  
  await page.waitForNavigation({ waitUntil: 'networkidle0' });
  console.log('Navigated to:', page.url());
  
  await page.goto('http://localhost:3000/projects/53caa13b-dd28-46d9-9fde-3f744958ab90/train');
  console.log('Visiting training page...');
  
  await page.waitForTimeout(5000); // wait for 5 seconds to capture logs
  
  await browser.close();
})();
