const puppeteer = require('puppeteer');
const { exec } = require('child_process');

(async () => {
  const server = exec('npx http-server -p 8091 -c-1 .');
  await new Promise(r => setTimeout(r, 2000));
  
  let result = {};
  
  try {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();
    
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
    
    await page.setCacheEnabled(false);
    const client = await page.target().createCDPSession();
    await client.send('Network.setBypassServiceWorker', { bypass: true });
    await client.send('Network.clearBrowserCache');
    
    // 1. DESKTOP VERIFICATION
    await page.setViewport({ width: 1200, height: 800 });
    console.log("Navigating to app...");
    await page.goto('http://localhost:8091', { waitUntil: 'networkidle0' });
    
    // Wait for login or dashboard
    await page.waitForFunction(() => {
      const login = document.getElementById('loginView');
      const dash = document.getElementById('dashboardView');
      return (login && !login.hidden) || (dash && !dash.hidden);
    }, { timeout: 10000 });
    
    const isLoginVisible = await page.evaluate(() => {
      const login = document.getElementById('loginView');
      return login && !login.hidden && getComputedStyle(login).display !== 'none';
    });
    
    if (isLoginVisible) {
      console.log("Logging in...");
      await page.type('#loginRoll', '2301031023009');
      await page.type('#loginPass', 'password123'); // Assuming standard test pass
      await page.click('#btnLogin');
      
      // Wait for dashboard
      await page.waitForFunction(() => {
        const dash = document.getElementById('dashboardView');
        return dash && !dash.hidden && getComputedStyle(dash).display !== 'none';
      }, { timeout: 15000 });
    }
    
    console.log("Dashboard loaded. Waiting for subjects...");
    // Give it a second to render data from Firestore
    await new Promise(r => setTimeout(r, 2000));
    
    // Check if BCS-551 is present
    await page.waitForSelector('.subject-card', { timeout: 10000 });
    
    // Extract BCS-551 data
    const desktopResult = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.subject-card'));
      const bcs551 = cards.find(c => c.innerText.includes('BCS-551') || c.innerText.includes('Database Management'));
      if (!bcs551) return null;
      
      return {
        html: bcs551.innerHTML,
        text: bcs551.innerText
      };
    });
    
    if (desktopResult) {
      console.log("✅ BCS-551 Subject Found on Desktop");
      console.log(desktopResult.text);
    } else {
      console.log("❌ BCS-551 Subject NOT found");
    }
    
    // 2. MOBILE VERIFICATION
    await page.setViewport({ width: 375, height: 812 });
    await new Promise(r => setTimeout(r, 1000));
    const mobileResult = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.subject-card'));
      const bcs551 = cards.find(c => c.innerText.includes('BCS-551') || c.innerText.includes('Database Management'));
      
      // Check horizontal overflow of body
      const overflow = document.documentElement.scrollWidth > window.innerWidth;
      return {
        found: !!bcs551,
        overflow: overflow,
        bodyWidth: document.documentElement.scrollWidth,
        windowWidth: window.innerWidth
      };
    });
    
    console.log("Mobile Verification:", mobileResult);
    
    // 3. PERSISTENCE VERIFICATION
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2000));
    
    const persistenceResult = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.subject-card'));
      const bcs551 = cards.find(c => c.innerText.includes('BCS-551') || c.innerText.includes('Database Management'));
      return !!bcs551;
    });
    
    console.log("Persistence Verification (after reload): BCS-551 Found =", persistenceResult);
    
    await browser.close();
  } catch (e) {
    console.error(e);
  } finally {
    server.kill();
  }
})();
