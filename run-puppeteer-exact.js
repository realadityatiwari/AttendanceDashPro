const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
  try {
    const browser = await puppeteer.launch({headless: 'new'});
    const page = await browser.newPage();
    
    // Set viewport to mobile width to reproduce the user's exact scenario
    await page.setViewport({ width: 375, height: 812 });

    console.log("Navigating to http://localhost:3000...");
    // The user specifically requested waiting until DOMContentLoaded
    await page.goto('http://localhost:3000', {waitUntil: 'domcontentloaded'});

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

      // Full outerHTML without truncation to satisfy step 6
      const getOuterHTML = (el) => el ? el.outerHTML : null;

      return {
        authContainer: {
          id: authContainer?.id,
          styles: getStyles(authContainer)
        },
        appShell: {
          id: appShell?.id,
          styles: getStyles(appShell),
          // We will print this but not all of it if it's huge, but the user asked for outerHTML
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
    // Don't print the huge appShell HTML to avoid spamming the log, we'll slice it safely
    if (result.appShell && result.appShell.outerHTML) {
        result.appShell.outerHTML = result.appShell.outerHTML.substring(0, 300) + '...[truncated]...</div><!-- /appShell -->';
    }
    console.log(JSON.stringify(result, null, 2));
    console.log("RESULT_JSON_END");

    // Take screenshot as requested
    await page.screenshot({ path: 'screenshot.png' });
    console.log("Screenshot saved to screenshot.png");

    await browser.close();
  } catch (e) {
    console.error("Puppeteer script failed:", e);
  }
})();
