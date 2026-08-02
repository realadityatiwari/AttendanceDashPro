const puppeteer = require('puppeteer');
const fs = require('fs');
const crypto = require('crypto');
const http = require('http');

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function fetchRaw(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ body: data, headers: res.headers }));
      res.on('error', reject);
    }).on('error', reject);
  });
}

(async () => {
  // ─── STEP 1: Hash disk file ───────────────────────────────────────────────
  const diskContent = fs.readFileSync('index.html', 'utf8');
  const diskHash = sha256(diskContent);
  console.log('\n=== STEP 1: SHA-256 HASHES ===');
  console.log('Disk file hash   :', diskHash);

  // ─── STEP 2: Hash HTTP response ───────────────────────────────────────────
  const { body: httpContent, headers } = await fetchRaw('http://localhost:3000/index.html');
  const httpHash = sha256(httpContent);
  console.log('HTTP served hash :', httpHash);
  console.log('Hashes match     :', diskHash === httpHash);
  console.log('Cache-Control    :', headers['cache-control'] || '(none)');
  console.log('ETag             :', headers['etag'] || '(none)');
  console.log('Last-Modified    :', headers['last-modified'] || '(none)');

  // ─── STEP 3: Print exact bottomNav & fabMark lines from HTTP body ─────────
  console.log('\n=== STEP 3: EXACT HTML FROM HTTP RESPONSE ===');
  const lines = httpContent.split('\n');
  lines.forEach((line, i) => {
    if (line.includes('bottomNav') || line.includes('fabMarkAttendance')) {
      console.log(`Line ${i + 1}: ${line.trimEnd()}`);
    }
  });

  // ─── STEP 4: Puppeteer – launch two viewports ─────────────────────────────
  console.log('\n=== STEP 4: PUPPETEER outerHTML ===');
  const browser = await puppeteer.launch({ headless: 'new' });

  // Mobile viewport (375px)
  const pageMobile = await browser.newPage();
  await pageMobile.setViewport({ width: 375, height: 812 });
  await pageMobile.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });

  const mobileResult = await pageMobile.evaluate(() => {
    const nav = document.getElementById('bottomNav');
    const fab = document.getElementById('fabMarkAttendance');
    const shell = document.getElementById('appShell');
    const cs = el => {
      const s = window.getComputedStyle(el);
      return { display: s.display, visibility: s.visibility };
    };
    return {
      viewport: window.innerWidth + 'x' + window.innerHeight,
      bottomNavOuterHTML: nav ? nav.outerHTML : 'NOT FOUND',
      bottomNavComputed: nav ? cs(nav) : null,
      fabOuterHTML: fab ? fab.outerHTML : 'NOT FOUND',
      fabComputed: fab ? cs(fab) : null,
      appShellComputed: shell ? cs(shell) : null
    };
  });

  console.log('\n[MOBILE 375px viewport]');
  console.log('Viewport         :', mobileResult.viewport);
  console.log('appShell computed:', JSON.stringify(mobileResult.appShellComputed));
  console.log('bottomNav outerHTML (first 200 chars):', mobileResult.bottomNavOuterHTML.substring(0, 200));
  console.log('bottomNav computed:', JSON.stringify(mobileResult.bottomNavComputed));
  console.log('fab outerHTML (first 200 chars):', mobileResult.fabOuterHTML.substring(0, 200));
  console.log('fab computed:', JSON.stringify(mobileResult.fabComputed));

  // Desktop viewport (1280px) – simulates what the user sees when they resize
  const pageDesktop = await browser.newPage();
  await pageDesktop.setViewport({ width: 1280, height: 800 });
  await pageDesktop.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });

  const desktopResult = await pageDesktop.evaluate(() => {
    const nav = document.getElementById('bottomNav');
    const fab = document.getElementById('fabMarkAttendance');
    const shell = document.getElementById('appShell');
    const cs = el => {
      const s = window.getComputedStyle(el);
      return { display: s.display, visibility: s.visibility };
    };
    return {
      viewport: window.innerWidth + 'x' + window.innerHeight,
      bottomNavOuterHTML: nav ? nav.outerHTML : 'NOT FOUND',
      bottomNavComputed: nav ? cs(nav) : null,
      fabComputed: fab ? cs(fab) : null,
      appShellComputed: shell ? cs(shell) : null
    };
  });

  console.log('\n[DESKTOP 1280px viewport]');
  console.log('Viewport         :', desktopResult.viewport);
  console.log('appShell computed:', JSON.stringify(desktopResult.appShellComputed));
  console.log('bottomNav outerHTML (first 200 chars):', desktopResult.bottomNavOuterHTML.substring(0, 200));
  console.log('bottomNav computed:', JSON.stringify(desktopResult.bottomNavComputed));
  console.log('fab computed:', JSON.stringify(desktopResult.fabComputed));

  // ─── STEP 5: Resize from desktop to mobile within same page ───────────────
  console.log('\n=== STEP 5: RESIZE desktop→mobile on SAME PAGE ===');
  await pageDesktop.setViewport({ width: 375, height: 812 });
  // Wait one tick for CSS media queries to recompute
  await new Promise(r => setTimeout(r, 200));

  const afterResize = await pageDesktop.evaluate(() => {
    const nav = document.getElementById('bottomNav');
    const fab = document.getElementById('fabMarkAttendance');
    const shell = document.getElementById('appShell');
    const cs = el => {
      const s = window.getComputedStyle(el);
      return { display: s.display, visibility: s.visibility };
    };
    return {
      viewport: window.innerWidth + 'x' + window.innerHeight,
      bottomNavComputed: nav ? cs(nav) : null,
      fabComputed: fab ? cs(fab) : null,
      appShellComputed: shell ? cs(shell) : null,
      bottomNavInlineStyle: nav ? nav.getAttribute('style') : null,
      fabInlineStyle: fab ? fab.getAttribute('style') : null
    };
  });

  console.log('After resize to 375px:');
  console.log('  Viewport         :', afterResize.viewport);
  console.log('  appShell computed:', JSON.stringify(afterResize.appShellComputed));
  console.log('  bottomNav inline style attr:', afterResize.bottomNavInlineStyle);
  console.log('  bottomNav computed:', JSON.stringify(afterResize.bottomNavComputed));
  console.log('  fab inline style attr:', afterResize.fabInlineStyle);
  console.log('  fab computed:', JSON.stringify(afterResize.fabComputed));

  await browser.close();
  console.log('\n=== DONE ===');
})();
