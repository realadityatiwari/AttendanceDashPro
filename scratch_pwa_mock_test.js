const puppeteer = require('puppeteer-core');

(async () => {
  const executablePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath,
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = (await browser.pages())[0];
  
  // Mock Firebase to bypass real auth and force logged-in state
  await page.evaluateOnNewDocument(() => {
    window.firebase = {
      apps: [],
      initializeApp: () => {},
      app: () => ({ options: { projectId: 'mock-project' } }),
      SDK_VERSION: 'MOCK',
      auth: () => ({
        setPersistence: () => Promise.resolve(),
        onAuthStateChanged: (cb) => {
          // Immediately simulate a logged in user
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
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle0' });

  // Wait for dashboard view to become visible
  await page.waitForSelector('#appShell', { visible: true });
  console.log("Dashboard loaded successfully!");

  // Viewport tests
  const viewports = [
    { width: 375, height: 812, name: 'Mobile' },
    { width: 768, height: 1024, name: 'Tablet' },
    { width: 1440, height: 900, name: 'Desktop' }
  ];

  for (const vp of viewports) {
    await page.setViewport(vp);
    // Give it a moment to reflow
    await new Promise(r => setTimeout(r, 500));
    
    const isBottomNavVisible = await page.evaluate(() => {
      const el = document.getElementById('bottomNav');
      return el && window.getComputedStyle(el).display !== 'none';
    });
    
    console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}): Bottom Nav Visible? ${isBottomNavVisible}`);
    
    // Test tabs
    if (vp.width === 375) {
      console.log("Testing mobile navigation...");
      await page.click('button[data-view="subjects"]');
      await new Promise(r => setTimeout(r, 200));
      const activeTab = await page.evaluate(() => document.querySelector('.nav-tab.active').getAttribute('data-view'));
      console.log("Active Tab after click:", activeTab);
      
      // Go back to dashboard
      await page.click('button[data-view="dashboard"]');
    }
  }

  // Offline transition test
  console.log("Setting offline mode...");
  const client = await page.target().createCDPSession();
  await client.send('Network.enable');
  await client.send('Network.emulateNetworkConditions', {
    offline: true,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
  });

  // Since we use mock firebase, the SW isn't bypassing our mock (because SW intercepts network requests, not globals).
  // Let's reload offline
  console.log("Reloading offline...");
  await page.reload({ waitUntil: 'networkidle0' }).catch(() => {});
  
  const offlineTitle = await page.title();
  console.log("Offline Title:", offlineTitle);
  
  const dashboardVisibleOffline = await page.evaluate(() => {
    const el = document.getElementById('appShell');
    return el && window.getComputedStyle(el).display !== 'none';
  });
  console.log("Dashboard visible offline?", dashboardVisibleOffline);

  await browser.close();
})();
