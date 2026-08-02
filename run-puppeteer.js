const puppeteer = require('puppeteer');

(async () => {
  try {
    const browser = await puppeteer.launch({headless: 'new'});
    const page = await browser.newPage();
    
    // Set viewport to mobile width to reproduce
    await page.setViewport({ width: 375, height: 812 });

    console.log("Navigating to http://localhost:3000...");
    await page.goto('http://localhost:3000', {waitUntil: 'networkidle0'});

    await new Promise(resolve => setTimeout(resolve, 1000));

    const result = await page.evaluate(() => {
      const authContainer = document.getElementById("authContainer");
      const appShell = document.getElementById("appShell");
      const bottomNav = document.getElementById("bottomNav");
      const fabMarkAttendance = document.getElementById("fabMarkAttendance");

      const getStyles = (el) => {
        if (!el) return null;
        const s = window.getComputedStyle(el);
        return {
          display: s.display,
          visibility: s.visibility,
          opacity: s.opacity,
          position: s.position,
          zIndex: s.zIndex
        };
      };

      const getBounds = (el) => el ? el.getBoundingClientRect().toJSON() : null;

      // Extract only first 200 chars of outerHTML to prevent massive output
      const getOuterHTML = (el) => {
        if (!el) return null;
        const html = el.outerHTML;
        return html.length > 500 ? html.substring(0, 500) + '...' : html;
      };

      return {
        authContainer: {
          id: authContainer?.id,
          styles: getStyles(authContainer)
        },
        appShell: {
          id: appShell?.id,
          styles: getStyles(appShell),
          outerHTML: getOuterHTML(appShell)
        },
        bottomNav: {
          id: bottomNav?.id,
          parentId: bottomNav?.parentElement?.id,
          styles: getStyles(bottomNav),
          bounds: getBounds(bottomNav),
          appShellContains: appShell ? appShell.contains(bottomNav) : false,
          outerHTML: getOuterHTML(bottomNav)
        },
        fabMarkAttendance: {
          id: fabMarkAttendance?.id,
          parentId: fabMarkAttendance?.parentElement?.id,
          styles: getStyles(fabMarkAttendance),
          bounds: getBounds(fabMarkAttendance),
          appShellContains: appShell ? appShell.contains(fabMarkAttendance) : false,
          outerHTML: getOuterHTML(fabMarkAttendance)
        }
      };
    });

    console.log("RESULT_JSON_START");
    console.log(JSON.stringify(result, null, 2));
    console.log("RESULT_JSON_END");

    await page.screenshot({ path: 'screenshot.png' });
    await browser.close();
  } catch (e) {
    console.error("Puppeteer script failed:", e);
  }
})();
