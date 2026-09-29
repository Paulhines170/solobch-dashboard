const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..');
for (const filename of ['dashboard.html', 'demo.html']) {
  const html = fs.readFileSync(path.join(root, filename), 'utf8');
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  if (scripts.length !== 1) throw new Error(`${filename}: expected one inline script`);
  new vm.Script(scripts[0], {filename});
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  if (new Set(ids).size !== ids.length) throw new Error(`${filename}: duplicate IDs`);
  for (const [, id] of scripts[0].matchAll(/\$\('([^']+)'\)/g)) {
    if (!ids.includes(id)) throw new Error(`${filename}: missing element ${id}`);
  }
  if (filename === 'demo.html' && /\bfetch\s*\(|XMLHttpRequest|WebSocket/.test(scripts[0])) {
    throw new Error('Demo must not make network requests');
  }
  if (filename === 'dashboard.html' && /DEMO DATA|demo-worker|recent_share_difficulties:\s*\[/.test(html)) {
    throw new Error('Fictional data must not be in the live dashboard');
  }
  console.log(`PASS ${filename}: script parses; element references present`);
}
