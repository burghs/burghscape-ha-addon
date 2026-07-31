import assert from "node:assert/strict";
import fs from "node:fs";
const source=fs.readFileSync(new URL("../src/pages/ClientGuides.jsx",import.meta.url),"utf8");
for(const [label,text] of [["header upload","actions={<Button"],["empty state","Upload First Guide"],["drag/drop","onDrop={e=>"],["types","image/png,image/jpeg,image/webp,application/pdf"],["edit","Save Changes"],["publish","Unpublish"],["featured","Remove Featured"],["assign","Assign Clients"],["replace","Replace File"],["delete confirmation","This action cannot be undone"],["PDF preview","<iframe"],["responsive cards","md:grid-cols-2 2xl:grid-cols-3"],["updated","Last updated"],["proxy error detail","HTTP ${r.status}"],["modal error","editorError&&"],["upload loading","Uploading…"]])assert.ok(source.includes(text),`Missing ${label}`);
assert.ok(!source.includes("storage_path"),"Internal storage paths must not render");
console.log("Client Guides CMS checks passed (17)");
