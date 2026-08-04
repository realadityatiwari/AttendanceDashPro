const fs = require('fs');
const acorn = require('acorn');

const content = fs.readFileSync('c:/Coding/AttendanceDashPro/js/ui.js', 'utf8');

try {
  acorn.parse(content, { ecmaVersion: 2022, sourceType: 'module' });
  console.log('No syntax errors found.');
} catch (e) {
  console.error('Syntax error at line', e.loc.line, 'col', e.loc.column);
  console.error(e.message);
}
