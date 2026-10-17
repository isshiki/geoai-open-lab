const { chromium } = require('playwright');
const fs=require('fs'); const path=require('path');
(async()=>{
 const out=path.resolve(__dirname,'../data/cache/embedding/tokyo-v1');
 const browser=await chromium.launch({...(process.env.BROWSER_EXECUTABLE ? {executablePath:process.env.BROWSER_EXECUTABLE} : {}),headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:900},deviceScaleFactor:1});
 await page.route('http://**/*',route=>route.abort());
 await page.route('https://**/*',route=>route.abort());
 for(const name of ['embedding_flow','representations','neighbors','dimensions','clusters','latent_axes','cover_1600x900']){
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
 await page.goto('file:///'+path.join(out,'08_region_embedding.html').replaceAll('\\','/'));
 await page.evaluate(()=>document.fonts.ready);
 if(await page.locator('.output_error').count())throw Error('Notebook error rendered');
 await page.screenshot({path:path.join(out,'html-preview.png')});
 const heading=page.getByText('2. 吉祥寺のトップ10を並べる',{exact:false}).first();
 await heading.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(out,'html-ranking-preview.png')});
 await browser.close();console.log('7 PNG files rendered; text bounds and HTML checked');
})().catch(e=>{console.error(e);process.exit(1)});
