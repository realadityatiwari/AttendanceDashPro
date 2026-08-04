const fs = require('fs');
const path = require('path');
const jsDir = 'c:/Coding/AttendanceDashPro/js';
const files = fs.readdirSync(jsDir);
const set = new Set(files);
files.filter(f => f.endsWith('.js')).forEach(f => {
  const code = fs.readFileSync(path.join(jsDir, f), 'utf8');
  const imports = code.match(/from\s+['"](\.\/[^'"]+)['"]/g) || [];
  imports.forEach(imp => {
    const matched = imp.match(/from\s+['"]\.\/([^'"]+)['"]/);
    if (matched) {
      const importedFile = matched[1];
      if (!set.has(importedFile)) {
        console.log('Case mismatch or missing in', f, '->', importedFile);
      }
    }
  });
});
