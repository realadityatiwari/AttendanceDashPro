import { JSDOM } from 'jsdom';
const dom = new JSDOM(`<!DOCTYPE html><html><body>
  <div id="panels"></div>
  <div id="mobileHeroContainer"></div>
  <div id="historyList"></div>
  <div id="historyCount"></div>
  <div id="mobileHistoryList"></div>
  <div id="subjectsViewContent"></div>
</body></html>`, { url: 'http://localhost/' });
global.window = dom.window;
global.document = dom.window.document;
global.firebase = {
  initializeApp: () => ({}),
  auth: () => ({}),
  firestore: () => ({})
};

import('./js/ui.js').then(async (ui) => {
  console.log('Test setup ready.');
}).catch(console.error);
