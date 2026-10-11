import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import ts from 'typescript'
import { chromium, devices } from 'playwright'
const source=await fs.readFile(new URL('../src/utils/bridgeAuth.ts',import.meta.url),'utf8')
const connect=await fs.readFile(new URL('../device_connect.html',import.meta.url),'utf8')
const script=ts.transpileModule(source.replace(/^import .*$/m,"function getBridgeUrl(){return ''}").replace(/export /g,'')+'\nwindow.qa={bridgeFetch,saveBridgeKey};',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
const browser=await chromium.launch()
try{
 for(const name of ['Pixel 7','iPhone 13','Desktop Chrome']){
  const context=await browser.newContext({...devices[name]});const page=await context.newPage();page.setDefaultTimeout(10000)
  let executions=0,attempts=0,approved=false,leaked=false
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url());const authenticated=(req.headers().cookie||'').includes('aurora_device=fixture-device')
   if(url.hostname==='external.test'){leaked=!!req.headers().authorization||!!req.headers().cookie;return route.fulfill({headers:{'Access-Control-Allow-Origin':'*'},body:'external'})}
   if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:`<meta charset="utf-8"><textarea>brouillon</textarea><script>${script}</script>`})
   if(url.pathname==='/connect')return route.fulfill({contentType:'text/html',body:connect})
   if(url.pathname==='/api/devices/session')return route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,connected:authenticated})})
   if(url.pathname==='/api/devices/pair')return route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,claim:'fixture-claim',code:'343434'})})
   if(url.pathname==='/api/devices/claim')return route.fulfill({contentType:'application/json',headers:approved?{'Set-Cookie':'aurora_device=fixture-device; Path=/; HttpOnly; SameSite=Strict'}:{},body:JSON.stringify({ok:true,connected:approved})})
   if(url.pathname.endsWith('/run-async'))attempts++
   if(!authenticated)return route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({error:'forbidden_public'})})
   if(url.pathname.endsWith('/run-async'))executions++
   await route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,jobId:'one',events:[]})})
  })
  await page.goto('http://fixture.test/');await page.locator('textarea').fill('generation conservee')
  await page.evaluate(()=>{window.result=window.qa.bridgeFetch('/api/python/run-async',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scriptPath:'fixture.py',args:[]})}).then(r=>r.json())})
  await page.getByRole('dialog',{name:'Connexion Aurora'}).waitFor()
  const phone=page.frameLocator('iframe');await phone.getByRole('button',{name:'Connecter mon appareil'}).click()
  await phone.locator('#code').waitFor();assert.equal(await phone.locator('#code').textContent(),'343434');assert.equal(executions,0)
  approved=true
  assert.equal((await page.evaluate(()=>Promise.race([window.result,new Promise((_,r)=>setTimeout(()=>r(Error('Pairing timeout')),10000))]))).jobId,'one')
  assert.equal(executions,1);assert.equal(attempts,2)
  await page.evaluate(async()=>{await window.qa.bridgeFetch('/api/python/job/one');await window.qa.bridgeFetch('http://external.test/api/check')})
  assert.equal(leaked,false);assert.equal(await page.locator('textarea').inputValue(),'generation conservee')
  assert.equal(await page.evaluate(()=>document.cookie.includes('aurora_device')),false)
  await context.close();console.log(name+': keyless approval, retained draft, one execution, authenticated polling, HttpOnly cookie, no external credential leak')
 }
}finally{await browser.close()}
