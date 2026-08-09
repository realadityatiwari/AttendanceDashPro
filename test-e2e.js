const puppeteer = require('puppeteer-core');

async function runTests() {
  const executablePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath,
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const logs = [];
  page.on('console', msg => logs.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', err => logs.push({ type: 'error', text: err.toString() }));

  // Mock Firebase to bypass real auth and simulate a clean session, then log in
  await page.evaluateOnNewDocument(() => {
    window.firebase = {
      apps: [],
      initializeApp: () => {},
      app: () => ({ options: { projectId: 'mock-project' } }),
      SDK_VERSION: 'MOCK',
      auth: () => ({
        setPersistence: () => Promise.resolve(),
        onAuthStateChanged: (cb) => {
          window._authCb = cb;
          setTimeout(() => cb(null), 100);
        },
        currentUser: null
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
    window.mockLogin = () => {
      window.firebase.auth().currentUser = { uid: 'mock_user_123' };
      window._authCb({ uid: 'mock_user_123' });
    };
  });

  console.log("Loading app...");
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle0' });

  // Verify auth container is visible
  const authVisible = await page.$eval('#authContainer', el => window.getComputedStyle(el).display !== 'none');
  console.log("Auth Visible (Clean Session):", authVisible);

  // Trigger login
  console.log("Mocking Login...");
  await page.evaluate(() => window.mockLogin());
  
  await page.waitForSelector('#appShell', { visible: true });
  console.log("Dashboard Loaded!");

  // Step 3: Attendance + Quiz Integration
  console.log("Testing Attendance + Quiz...");
  await page.evaluate(() => {
    // switch to QUIZ 1
    const tabs = document.querySelectorAll('.tab-btn');
    if (tabs.length > 0) tabs[0].click();
  });
  
  // Get initial % 
  const initialPct = await page.$eval('#todayClassesList', el => el.innerHTML); // just testing logic
  // We'll mutate attendance programmatically to avoid complex selectors
  await page.evaluate(() => {
    // Log a present for first subject today
    const dateStr = window.uiGetTodayString ? window.uiGetTodayString() : new Date().toISOString().split('T')[0];
    if (window.logClassState) {
        window.logClassState(dateStr, 'BCS-051', 'L', 'PRESENT');
    } else {
        // Fallback to UI click if possible
        const presentBtn = document.querySelector('.action-btn.present');
        if (presentBtn) presentBtn.click();
    }
  });
  await new Promise(r => setTimeout(r, 500));
  
  // Step 4: Laboratory + Attendance
  console.log("Testing Laboratory...");
  await page.evaluate(() => {
    document.querySelector('button[data-view="subjects"]').click();
  });
  await new Promise(r => setTimeout(r, 500));
  
  // Step 5: Academic Events
  console.log("Testing Academic Events...");
  await page.evaluate(() => {
    if (window.openEventForm) window.openEventForm();
  });
  await new Promise(r => setTimeout(r, 500));
  
  const eventFormVisible = await page.$eval('#eventFormOverlay', el => window.getComputedStyle(el).display !== 'none').catch(() => false);
  console.log("Event Form Visible:", eventFormVisible);
  
  await page.evaluate(() => {
    document.getElementById('eventFormOverlay').style.display = 'none';
  });

  // Step 7: Responsive
  console.log("Testing Viewports...");
  const viewports = [
    { width: 375, height: 812, name: 'Mobile' },
    { width: 768, height: 1024, name: 'Tablet' },
    { width: 1440, height: 900, name: 'Desktop' }
  ];
  for (const vp of viewports) {
    await page.setViewport(vp);
    await new Promise(r => setTimeout(r, 500));
    const navVisible = await page.$eval('#bottomNav', el => window.getComputedStyle(el).display !== 'none').catch(() => false);
    console.log(`Viewport ${vp.width}: BottomNav = ${navVisible}`);
  }
  
  console.log("Logs during run:");
  const errLogs = logs.filter(l => l.type === 'error' || l.type === 'warning');
  console.log(errLogs);

  await browser.close();
}

runTests().catch(console.error);
