const fs = require("fs");

const html = fs.readFileSync("frontend-preview.html", "utf8");
const scriptMatch = html.match(/<script>([\s\S]*)<\/script>/);
if (!scriptMatch) throw new Error("Inline script not found");
new Function(scriptMatch[1]);

const ids = Array.from(html.matchAll(/\sid="([^"]+)"/g), (match) => match[1]);
const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
if (duplicates.length) throw new Error(`Duplicate ids: ${Array.from(new Set(duplicates)).join(", ")}`);

for (const id of ["routing-form", "source-form", "network-form", "security-form"]) {
  if (!ids.includes(id)) throw new Error(`Missing settings form: ${id}`);
}

console.log(`frontend preview ok: ${ids.length} unique ids`);
