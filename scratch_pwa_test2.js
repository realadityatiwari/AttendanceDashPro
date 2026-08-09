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
  
  // Fill login
  console.log("Typing credentials...");
  await page.type('#loginRoll', '1234567890123');
  await page.type('#loginPass', 'password');
  
  // We can't actually log in to Firebase because this is a dummy account and the SDK is loaded from the network (Firebase is real).
  // Oh wait, in previous steps, Firebase was mocked or used a dummy project?
  // test-persistence-sync.js said `[firebase.js] Firebase SDK version: STUB`.
  // Wait, let's check `firebase.js` to see if it's stubbed or real.
  
  const fbIsStub = await page.evaluate(() => {
    return window.auth && window.auth.currentUser ? true : false;
  });
  console.log("Is FB stubbed/logged in?", fbIsStub);
  
  await browser.close();
})();
