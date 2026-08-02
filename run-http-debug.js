const http = require('http');

function fetch(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({
        statusCode: res.statusCode,
        headers: res.headers,
        body: data,
        bodyLength: data.length
      }));
      res.on('error', reject);
    }).on('error', reject);
  });
}

(async () => {
  // Try root URL (no redirect following, manual)
  console.log('--- Fetching http://localhost:3000 ---');
  const root = await fetch('http://localhost:3000');
  console.log('Status:', root.statusCode);
  console.log('Headers:', JSON.stringify(root.headers, null, 2));
  console.log('Body length:', root.bodyLength);
  if (root.bodyLength > 0) {
    // Find bottomNav and fabMarkAttendance lines
    const lines = root.body.split('\n');
    console.log('\nLines containing bottomNav or fabMarkAttendance:');
    lines.forEach((line, i) => {
      if (line.includes('bottomNav') || line.includes('fabMarkAttendance')) {
        console.log(`  Line ${i + 1}: ${line.trimEnd()}`);
      }
    });
    // Print first 500 chars of body
    console.log('\nFirst 500 chars of body:');
    console.log(root.body.substring(0, 500));
  }

  // Try /index.html explicitly
  console.log('\n--- Fetching http://localhost:3000/index.html ---');
  const indexPage = await fetch('http://localhost:3000/index.html');
  console.log('Status:', indexPage.statusCode);
  console.log('Headers:', JSON.stringify(indexPage.headers, null, 2));
  console.log('Body length:', indexPage.bodyLength);
  if (indexPage.bodyLength > 0) {
    const lines = indexPage.body.split('\n');
    console.log('\nLines containing bottomNav or fabMarkAttendance:');
    lines.forEach((line, i) => {
      if (line.includes('bottomNav') || line.includes('fabMarkAttendance')) {
        console.log(`  Line ${i + 1}: ${line.trimEnd()}`);
      }
    });
  }
})();
