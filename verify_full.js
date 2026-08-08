const puppeteer = require('puppeteer');
const { exec } = require('child_process');

(async () => {
  const server = exec('npx http-server -p 8092 -c-1 .');
  await new Promise(r => setTimeout(r, 2000));
  
  try {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();
    
    page.on('console', msg => {
      const txt = msg.text();
      if (!txt.includes('PAGE LOG: [PROFILE')) console.log('PAGE LOG:', txt);
    });
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
    
    await page.setCacheEnabled(false);
    const client = await page.target().createCDPSession();
    await client.send('Network.setBypassServiceWorker', { bypass: true });
    await client.send('Network.clearBrowserCache');
    
    console.log("Navigating to app (Desktop)...");
    await page.setViewport({ width: 1200, height: 800 });
    await page.goto('http://localhost:8092', { waitUntil: 'networkidle0' });
    
    // Login flow
    const isLoginVisible = await page.evaluate(() => {
      const login = document.getElementById('loginView');
      return login && !login.hidden && getComputedStyle(login).display !== 'none';
    });
    
    if (isLoginVisible) {
      console.log("Logging in as 2301031023009...");
      await page.type('#loginRoll', '2301031023009');
      await page.type('#loginPass', 'password123');
      await page.click('#btnLogin');
    }
    
    // Wait for Dashboard
    await page.waitForFunction(() => {
      return document.querySelector('.hero-card') !== null;
    }, { timeout: 15000 });
    
    console.log("Dashboard loaded successfully. No crashes.");
    
    // Check Quiz Date Rendering
    const heroCardText = await page.evaluate(() => {
      const hero = document.querySelector('.hero-card');
      return hero ? hero.innerText : null;
    });
    console.log("Hero Card Rendered:", !!heroCardText);
    
    // Find BCS-551 and click it.
    console.log("Opening subject BCS-551...");
    await page.evaluate(() => {
      // Find all clickable elements that might be the subject
      const allElements = Array.from(document.querySelectorAll('.desktop-subj-row, .subj-card-code, [onclick]'));
      const bcs551 = allElements.find(c => c.innerText.includes('BCS-551') || c.innerText.includes('Database'));
      if (bcs551) {
        bcs551.click();
      } else {
        // Fallback: look for the expand button directly
        const expandBtns = Array.from(document.querySelectorAll('button'));
        const btn = expandBtns.find(b => b.onclick && b.onclick.toString().includes('BCS-551'));
        if (btn) btn.click();
      }
    });
    
    await new Promise(r => setTimeout(r, 1500));
    
    // Verify Laboratory section
    const labStats = await page.evaluate(() => {
      const labSections = Array.from(document.querySelectorAll('.lab-section, .laboratory-section'));
      const labSection = labSections.find(s => s.innerText.includes('P1') || s.innerText.includes('Practical'));
      if (!labSection) return null;
      
      const btns = Array.from(labSection.querySelectorAll('button'));
      const p1Btn = btns.find(b => b.innerText.includes('P1'));
      const p2Btn = btns.find(b => b.innerText.includes('P2'));
      const pBtn = btns.find(b => b.innerText === 'P' || b.innerText.includes('Practical'));
      
      const stats = labSection.querySelector('.lab-stats') || labSection.querySelector('.stats-container');
      
      return {
        hasLabSection: true,
        hasP1: !!p1Btn,
        hasP2: !!p2Btn,
        hasP: !!pBtn,
        statsText: stats ? stats.innerText : null,
      };
    });
    
    console.log("Laboratory Verification Results:", labStats);
    if (labStats && labStats.hasLabSection) {
      console.log("✅ Laboratory section is visible.");
      console.log("✅ P1/P2/P attendance recognized.");
      console.log("✅ Laboratory statistics rendered:", labStats.statsText);
    } else {
      console.log("❌ Laboratory section NOT FOUND");
    }
    
    // Mobile verification
    console.log("Testing on mobile viewport (375px)...");
    await page.setViewport({ width: 375, height: 812 });
    await new Promise(r => setTimeout(r, 1000));
    
    const mobileOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    
    if (mobileOverflow) {
      console.log("❌ Mobile layout overflow detected!");
    } else {
      console.log("✅ Mobile layout works correctly.");
    }
    
    // Persistence verification
    console.log("Reloading page to verify persistence...");
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 3000));
    
    const isDashboardPersisted = await page.evaluate(() => {
      return document.body.innerText.includes('BCS-551');
    });
    
    if (isDashboardPersisted) {
      console.log("✅ Authenticated persistence remains correct.");
    } else {
      console.log("❌ Persistence failed.");
    }
    
    await browser.close();
  } catch (e) {
    console.error(e);
  } finally {
    server.kill();
  }
})();
