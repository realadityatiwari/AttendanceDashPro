function parseDateString(str) {
  const parts = str.split('-');
  if (parts.length !== 3) return null;
  const d = new Date(+parts[0], +parts[1] - 1, +parts[2]);
  d.setHours(12, 0, 0, 0);
  return d;
}
function formatTodayHeader(dateVal) {
  let date = dateVal;
  if (typeof dateVal === 'string') {
    date = parseDateString(dateVal);
  }
  if (!date || typeof date.toLocaleDateString !== 'function') {
    date = new Date(dateVal);
    if (isNaN(date.getTime())) return String(dateVal);
  }
  try {
    const dName = date.toLocaleDateString('en-US', { weekday: 'long' });
    const dStr  = date.toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' });
    return `${dName} • ${dStr}`;
  } catch(e) {
    return String(dateVal);
  }
}
console.log(formatTodayHeader('2026-07-20'));
console.log(formatTodayHeader(new Date()));
console.log(formatTodayHeader({}));
console.log(formatTodayHeader(null));
console.log(formatTodayHeader(undefined));
