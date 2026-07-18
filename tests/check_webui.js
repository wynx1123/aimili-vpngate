const fs = require("fs");
const path = require("path");

const root = path.resolve("webui");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const js = fs.readFileSync(path.join(root, "assets", "app.js"), "utf8");
const css = fs.readFileSync(path.join(root, "assets", "app.css"), "utf8");
new Function(js);

const ids = Array.from(html.matchAll(/\sid="([^"]+)"/g), (match) => match[1]);
const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
if (duplicateIds.length) throw new Error(`Duplicate ids: ${[...new Set(duplicateIds)].join(", ")}`);

for (const id of ["routing-form", "source-form", "network-form", "security-form", "source-name", "node-rows", "settings-backdrop"]) {
  if (!ids.includes(id)) throw new Error(`Missing required UI element: ${id}`);
}
for (const [, id] of js.matchAll(/\$\("([^"]+)"\)/g)) {
  if (!ids.includes(id)) throw new Error(`JavaScript references missing element: ${id}`);
}
if (!html.includes('./assets/app.css') || !html.includes('./assets/app.js')) throw new Error("Static asset links missing");
if (!css.includes(".route-stage")) throw new Error("Primary route-stage styles missing");
console.log(`webui ok: ${ids.length} unique ids, ${js.length} bytes JavaScript`);