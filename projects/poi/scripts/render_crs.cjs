const { chromium } = require('playwright');
const fs=require('fs'); const path=require('path');
(async()=>{
 const base=path.resolve(__dirname,'../data/cache');
 const browser=await chromium.launch({...(process.env.BROWSER_EXECUTABLE ? {executablePath:process.env.BROWSER_EXECUTABLE} : {}),headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:900},deviceScaleFactor:1});
 await page.route('http://**/*',route=>route.abort());
 await page.route('https://**/*',route=>route.abort());
 for(const folder of ['crs/kichijoji-v1']){
 const out=path.join(base,folder);
 for(const name of fs.readdirSync(out).filter(n=>n.endsWith('.svg')).map(n=>n.slice(0,-4))){
  const svg=fs.readFileSync(path.join(out,name+'.svg'),'utf8');
  await page.setContent('<html lang="ja"><meta charset="utf-8"><body style="margin:0">'+svg+'</body></html>');
  await page.evaluate(()=>document.fonts.ready);
  const clipped=await page.locator('svg text').evaluateAll(nodes=>nodes.filter(n=>{const b=n.getBBox();return b.x<0||b.x+b.width>1600||b.y<0||b.y+b.height>900}).map(n=>n.textContent));
  if(clipped.length)throw Error('Clipped text '+name+': '+clipped.join(','));
  await page.screenshot({path:path.join(out,name+'.png')});
  if(name==='cover_1600x900'){
   await page.setViewportSize({width:800,height:450});
   await page.addStyleTag({content:'svg{width:800px;height:450px}'});
   await page.screenshot({path:path.join(out,'cover-preview-800.png')});
   await page.setViewportSize({width:1600,height:900});
  }
 }
 }
 const html=path.join(base,'crs/kichijoji-v1/14_crs.html');
 if(fs.existsSync(html)){
  await page.goto('file:///'+html.replace(/\\/g,'/'));
  await page.screenshot({path:path.join(base,'crs/kichijoji-v1/html-intro-preview.png')});
  await page.locator('h2').filter({hasText:'POIを500m'}).scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(base,'crs/kichijoji-v1/html-results-preview.png')});
 }
 await browser.close();console.log('CRS figures rendered; SVG text bounds checked');
})().catch(e=>{console.error(e);process.exit(1)});
