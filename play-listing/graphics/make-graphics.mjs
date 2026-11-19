import { chromium } from "playwright"; import fs from "node:fs";
const [iconIn, logoSvg, outDir] = process.argv.slice(2);
const b = await chromium.launch();
// icon: RGBA 512×512
let p = await b.newPage({ viewport: { width: 512, height: 512 } });
await p.setContent(`<body style="margin:0;background:transparent"><img src="data:image/png;base64,${fs.readFileSync(iconIn).toString("base64")}" width=512 height=512 style="display:block"></body>`);
await p.screenshot({ path: outDir + "/icon-512.png", omitBackground: true });
// feature graphic 1024×500
p = await b.newPage({ viewport: { width: 1024, height: 500 } });
const logo = fs.readFileSync(logoSvg, "utf8");
await p.setContent(`<html><head><style>
body{margin:0;width:1024px;height:500px;background:radial-gradient(circle at 20% 30%,#1e3a5f 0,#0f172a 55%,#020617 100%);font-family:-apple-system,Inter,Helvetica,Arial,sans-serif;color:#fff;display:flex;align-items:center}
.wrap{display:flex;align-items:center;gap:56px;padding-left:96px}.logo svg{width:300px;height:auto}
h1{font-size:46px;margin:0 0 14px;font-weight:700;letter-spacing:-.5px}p{font-size:26px;margin:0;color:#cbd5e1;line-height:1.35}
</style></head><body><div class="wrap"><div class="logo">${logo}</div><div><h1>Private messages<br>and calls</h1><p>End-to-end encrypted chats,<br>groups and calls. By invitation.</p></div></div></body></html>`);
await p.screenshot({ path: outDir + "/feature-1024x500.png" });
await b.close();
