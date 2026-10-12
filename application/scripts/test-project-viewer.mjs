import assert from 'node:assert/strict'
import {spawn} from 'node:child_process'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {chromium,devices} from 'playwright'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const server=spawn(process.env.PYTHON||(process.platform==='win32'?'python':'python3'),[path.join(root,'tests_agi/project_viewer_fixture.py')],{cwd:root,env:{...process.env,PYTHONPATH:[root,process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)}})
server.stderr.on('data',()=>{})
let browser
try{
 const url=await new Promise((resolve,reject)=>{let buffer='';const timeout=setTimeout(()=>reject(Error('Fixture startup timed out')),30000);server.stdout.on('data',chunk=>{buffer+=chunk;const line=buffer.split('\n')[0];try{const data=JSON.parse(line);clearTimeout(timeout);resolve(data.url)}catch{}});server.once('exit',code=>{clearTimeout(timeout);reject(Error('Fixture exited: '+code))})})
 browser=await chromium.launch({headless:true,args:["--use-angle=swiftshader","--enable-unsafe-swiftshader"]})
 for(const device of ['Pixel 7','iPhone 13','iPad Mini','Desktop Chrome']){
  const context=await browser.newContext({...devices[device]});const page=await context.newPage(),errors=[]
  page.on('pageerror',e=>errors.push(e.message));await page.goto(url)
  await page.waitForFunction(()=>document.body.dataset.ready==='true')
  assert.equal(await page.locator('#meshes option').count(),1)
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  const canvas=page.locator('canvas');await page.waitForTimeout(250);const before=await canvas.screenshot()
  const box=await canvas.boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.75,box.y+box.height*.4,{steps:12});await page.mouse.up()
  let changed=false
  for(let attempt=0;attempt<20&&!changed;attempt++){await page.waitForTimeout(100);changed=!before.equals(await canvas.screenshot())}
  assert.equal(changed,true,'orbit changes the rendered real geometry')
  await page.getByRole('combobox',{name:'Aspect',exact:true}).selectOption('pure');await page.getByRole('button',{name:'Tout cadrer'}).click()
  assert.equal(await page.locator('body').getAttribute('data-ready'),'true');assert.deepEqual(errors,[])
  console.log(device+': real GLB, orbit, pure geometry and responsive layout passed');await context.close()
 }
}finally{await browser?.close();server.kill()}
