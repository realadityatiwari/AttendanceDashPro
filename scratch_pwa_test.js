const puppeteer = require('puppeteer-core');

(async () => {
  const executablePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath,
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = (await browser.pages())[0];
  
  console.log("Loading app...");
  await page.goto('http://localhost:8080/', { waitUntil: 'networkidle0' });
  
  console.log("Checking Service Worker registration...");
  const swHandle = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    return reg ? reg.active.state : null;
  });
  console.log("Service Worker State:", swHandle);
  
  if (swHandle === 'activated') {
    console.log("SW activated successfully. Setting offline mode...");
    const client = await page.target().createCDPSession();
    await client.send('Network.enable');
    await client.send('Network.emulateNetworkConditions', {
      offline: true,
      latency: 0,
      downloadThroughput: -1,
      uploadThroughput: -1,
    });
    
    console.log("Reloading offline...");
    await page.reload({ waitUntil: 'networkidle0' }).catch(() => {});
    
    const offlineTitle = await page.title();
    console.log("Offline Title:", offlineTitle);
    
    const hasAuthContainer = await page.evaluate(() => {
      const el = document.getElementById('authContainer');
      return el && window.getComputedStyle(el).display !== 'none';
    });
    console.log("Has Auth Container Offline?", hasAuthContainer);
    
    const isOfflineBannerVisible = await page.evaluate(() => {
        const el = document.getElementById('offlineBanner');
        return el && window.getComputedStyle(el).display !== 'none';
    });
    console.log("Is Offline Banner Visible?", isOfflineBannerVisible);
  }
  
  await browser.close();
})();
