const puppeteer = require('puppeteer-core');

(async () => {
  const executablePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath,
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = (await browser.pages())[0];
  
  await page.setRequestInterception(true);
  page.on('request', request => {
    if (request.url().includes('gstatic.com') || request.url().includes('firebase')) {
      request.abort();
    } else {
      request.continue();
    }
  });

  // Mock Firebase
  await page.evaluateOnNewDocument(() => {
    window.firebase = {
      apps: [],
      initializeApp: () => {},
      app: () => ({ options: { projectId: 'mock-project' } }),
      SDK_VERSION: 'MOCK',
      auth: () => ({
        setPersistence: () => Promise.resolve(),
        onAuthStateChanged: (cb) => {
          setTimeout(() => cb({ uid: 'mock_user_123' }), 100);
        },
        currentUser: { uid: 'mock_user_123' }
      }),
      firestore: () => ({
        collection: () => ({
          doc: () => ({
            get: () => Promise.resolve({ exists: false, data: () => ({}) }),
            set: () => Promise.resolve(),
            update: () => Promise.resolve()
          })
        })
      })
    };
    window.firebase.auth.Auth = { Persistence: { LOCAL: 'local' } };
  });

  console.log("Loading app...");
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle0', timeout: 60000 }).catch(e => console.error("Navigation error:", e));

  // Give some time for our mock to trigger auth state change
  await new Promise(r => setTimeout(r, 1000));
  
  const isDashboardVisible = await page.evaluate(() => {
    const shell = document.getElementById('appShell');
    return shell && window.getComputedStyle(shell).display !== 'none';
  });
  console.log("Dashboard visible?", isDashboardVisible);

  if (isDashboardVisible) {
    const viewports = [
      { width: 375, height: 812, name: 'Mobile' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 1440, height: 900, name: 'Desktop' }
    ];

    for (const vp of viewports) {
      await page.setViewport(vp);
      await new Promise(r => setTimeout(r, 500));
      
      const isBottomNavVisible = await page.evaluate(() => {
        const el = document.getElementById('bottomNav');
        return el && window.getComputedStyle(el).display !== 'none';
      });
      console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}): Bottom Nav Visible? ${isBottomNavVisible}`);
      
      if (vp.width === 375) {
        console.log("Testing mobile navigation...");
        await page.click('button[data-view="subjects"]');
        await new Promise(r => setTimeout(r, 200));
        const activeTab = await page.evaluate(() => document.querySelector('.nav-tab.active')?.getAttribute('data-view'));
        console.log("Active Tab after click:", activeTab);
        
        await page.click('button[data-view="dashboard"]');
      }
    }
  }

  await browser.close();
})();
