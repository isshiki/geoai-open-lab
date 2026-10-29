const { chromium } = require('playwright');
const fs=require('fs'),path=require('path');
(async()=>{
 const out=path.resolve(__dirname,'../data/cache/geojson/python-v1');
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:900},deviceScaleFactor:1});
 await page.route('http://**/*',r=>r.abort());await page.route('https://**/*',r=>r.abort());
 for(const filename of fs.readdirSync(out).filter(n=>n.endsWith('.svg'))){
  const svg=fs.readFileSync(path.join(out,filename),'utf8');
  await page.setViewportSize({width:1600,height:900});
  await page.setContent('<html lang="ja"><meta charset="utf-8"><body style="margin:0">'+svg+'</body></html>');
  await page.evaluate(()=>document.fonts.ready);await page.evaluate(()=>window.scrollTo(0,0));
  await page.waitForTimeout(200);
  const clipped=await page.locator('svg text').evaluateAll(ns=>ns.filter(n=>{const b=n.getBBox();return b.x<0||b.x+b.width>1600||b.y<0||b.y+b.height>900}).map(n=>n.textContent));
  if(clipped.length)throw Error(filename+': '+clipped.join(','));
  await page.locator('svg').screenshot({path:path.join(out,filename.replace('.svg','.png'))});
  const preview=await browser.newPage({viewport:{width:800,height:450},deviceScaleFactor:1});
  await preview.route('**/*',r=>r.abort());
  const small=svg.replace('width="1600" height="900"','width="800" height="450"');
  await preview.setContent('<html lang="ja"><meta charset="utf-8"><body style="margin:0">'+small+'</body></html>');
  await preview.evaluate(()=>document.fonts.ready);await preview.waitForTimeout(200);
  await preview.locator('svg').screenshot({path:path.join(out,filename.replace('.svg','_preview_800.png'))});
  await preview.close();
 }
 await page.setViewportSize({width:1400,height:1000});
 await page.goto('file:///'+path.join(out,'15_geojson.html').replace(/\\/g,'/'));
 await page.screenshot({path:path.join(out,'html-intro.png')});
 await page.getByRole('heading',{name:/4\. 誤り/}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(out,'html-results.png')});
 await page.getByRole('heading',{name:/6\. 地図/}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(out,'html-map.png')});
 await browser.close();console.log('Six SVG/PNG pairs and 800px previews rendered; text bounds checked');
})().catch(e=>{console.error(e);process.exit(1)});
