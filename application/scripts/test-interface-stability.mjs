import assert from 'node:assert/strict'
import http from 'node:http'
import ts from 'typescript'
import fs from 'node:fs/promises'
import { chromium, devices } from 'playwright'
const recovery=await fs.readFile(new URL('../src/utils/buildRecovery.ts',import.meta.url),'utf8')
const skin=await fs.readFile(new URL('../src/utils/uiSkin.ts',import.meta.url),'utf8')
const script=ts.transpileModule((recovery+'\n'+skin.replace(/^import .*$/m,'')).replace(/export /g,'')+'\nwindow.qa={installUiSkin,applyUiSkin,readUiSkin,markBootHealthy,recoverFromStaleBuild};installUiSkin();',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(`<div id="root"><textarea>mon travail</textarea></div><script>${script}</script>`)})
await new Promise(r=>server.listen(0,'127.0.0.1',r))
const browser=await chromium.launch()
try{
 for(const device of ['Pixel 7','iPhone 13','iPad Mini','Desktop Chrome']){
  const context=await browser.newContext({...devices[device]})
  const page=await context.newPage();await page.goto(`http://127.0.0.1:${server.address().port}`)
  await page.locator('textarea').fill('saisie en cours')
  let navigations=0;page.on('framenavigated',f=>{if(f===page.mainFrame())navigations++})
  const other=await context.newPage();await other.goto(page.url())
  await other.evaluate(()=>window.qa.applyUiSkin('aurora_v3'))
  await page.waitForTimeout(500)
  assert.equal(await page.evaluate(()=>window.qa.readUiSkin()),'aurora_v4')
  assert.equal(await page.locator('html').getAttribute('data-ui-skin'),'aurora_v4')
  await page.evaluate(()=>{window.qa.markBootHealthy();for(let i=0;i<4;i++)window.qa.recoverFromStaleBuild('failed to fetch dynamically imported module')})
  await page.waitForTimeout(500)
  assert.equal(navigations,0);assert.equal(await page.locator('textarea').inputValue(),'saisie en cours')
  assert.equal(await page.locator('#aurora-build-recovery-notice').count(),1)
  await other.close();await context.close();console.log(device+': cross-tab theme and repeated chunk errors preserve page and draft')
 }
 const portal=await fs.readFile(new URL('../persistent_workspace.html',import.meta.url),'utf8')
 for(const device of ['Pixel 7','iPhone 13']){
  const context=await browser.newContext({...devices[device]});const page=await context.newPage()
  await page.setContent('<body style="background:#141b2f">Aurora</body>')
  const image=(await page.screenshot({type:'jpeg'})).toString('base64')
  const actions=[];let polls=0
  await page.route('**/*',async route=>{
   const path=new URL(route.request().url()).pathname
   if(path==='/workspace')return route.fulfill({contentType:'text/html',body:portal})
   const data=route.request().postDataJSON()
   if(path.endsWith('/action'))actions.push(data)
   let body={ok:true,id:'same-session'}
   if(path.endsWith('/frame')){polls++;body={...body,image,viewport:{width:390,height:630},controls:[{id:'1',frame:'1',label:'Module actif',x:10,y:10,width:100,height:44}],tabs:[],assets:[],downloads:[],canvases:[]}}
   await route.fulfill({contentType:'application/json',body:JSON.stringify(body)})
  })
  await page.goto('http://127.0.0.1:3030/workspace');await page.locator('#key').fill('fixture-key');await page.locator('#connect').click()
  await page.waitForFunction(()=>document.querySelector('#controls button'))
  const original=page.viewportSize();await page.setViewportSize({...original,height:original.height-90});await page.waitForTimeout(700)
  assert.equal(actions.filter(a=>a.type==='resize').length,1,'Browser toolbar must not resize remote session')
  await page.evaluate(()=>{window.oldControl=document.querySelector('#controls button')});const stageBox=await page.locator('#stage').boundingBox();await page.mouse.move(stageBox.x+50,stageBox.y+100);await page.mouse.down()
  await page.waitForTimeout(1800)
  assert(await page.evaluate(()=>window.oldControl===document.querySelector('#controls button')),'Polling replaced the touched control')
  await page.mouse.up()
  await page.setViewportSize({width:844,height:390});await page.waitForTimeout(700)
  assert.equal(actions.filter(a=>a.type==='resize').length,2,'Orientation must resize remote session')
  assert(polls>=2);await context.close();console.log(device+': controller stable during toolbar resize, polling and gestures')
 }
}finally{await browser.close();await new Promise(r=>server.close(r))}
