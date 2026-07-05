import { fileURLToPath } from 'node:url'

const APP_URL = process.env.AURORA_APP_URL || 'http://127.0.0.1:4173/'
const DEBUG_URL = process.env.CDP_DEBUG_URL || 'http://127.0.0.1:9223'
const APP_MATCH = new URL(APP_URL).host
const REF_FILE = fileURLToPath(new URL('../test-outputs/probe_reference.svg', import.meta.url))

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitFor(c, expression, timeoutMs = 15000) {
  const startedAt = Date.now()
  let lastError = null
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const value = await c.eval(expression)
      if (value) return value
    } catch (err) {
      lastError = err
    }
    await sleep(250)
  }
  throw lastError || new Error(`Timed out waiting for ${expression}`)
}

async function connectPage(urlMatch, targetId = '') {
  const targets = await fetch(`${DEBUG_URL}/json/list`).then((r) => r.json())
  const page = (targetId ? targets.find((target) => target.id === targetId) : null)
    || [...targets].reverse().find((target) => target.type === 'page' && String(target.url || '').includes(urlMatch))
  if (!page) throw new Error(`No page target matching ${urlMatch}`)

  const ws = new WebSocket(page.webSocketDebuggerUrl)
  let id = 0
  const pending = new Map()
  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message)
      pending.delete(message.id)
    }
  })
  await new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('WS open timeout')), 8000)
    ws.addEventListener('open', () => { clearTimeout(t); resolve() })
    ws.addEventListener('error', reject)
  })

  const send = (method, params = {}) => {
    const messageId = ++id
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => {
        pending.delete(messageId)
        reject(new Error(`${method}: timeout`))
      }, 20000)
      pending.set(messageId, (message) => {
        clearTimeout(t)
        if (message.error) reject(new Error(`${method}: ${JSON.stringify(message.error)}`))
        else resolve(message.result)
      })
      ws.send(JSON.stringify({ id: messageId, method, params }))
    })
  }

  await send('Runtime.enable')
  await send('Page.enable').catch(() => {})
  const evaluate = async (expression, opts = {}) => {
    const result = await send('Runtime.evaluate', {
      expression,
      returnByValue: opts.byValue !== false,
      awaitPromise: true,
      userGesture: true,
    })
    if (result.exceptionDetails) {
      throw new Error('JS: ' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text))
    }
    return opts.byValue === false ? result.result : result.result?.value
  }
  const setFiles = async (selector, files) => {
    const result = await send('Runtime.evaluate', {
      expression: `document.querySelector(${JSON.stringify(selector)})`,
      returnByValue: false,
    })
    const objectId = result.result?.objectId
    if (!objectId) throw new Error(`File input not found: ${selector}`)
    await send('DOM.setFileInputFiles', { objectId, files })
  }
  return { send, eval: evaluate, setFiles, close: () => ws.close() }
}

const installFetchMocks = `
(() => {
  if (window.__auroraProbeInstalled) return true;
  window.__auroraProbeInstalled = true;
  window.__auroraProbe = { calls: [], workflows: [], interrupts: 0, frees: 0, uploads: 0 };
  const originalFetch = window.fetch.bind(window);
  const json = (data) => new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
  const ndjson = (text) => new Response(
    new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode(JSON.stringify({ response: text, done: false }) + '\\n'));
        controller.enqueue(encoder.encode(JSON.stringify({ response: '', done: true }) + '\\n'));
        controller.close();
      }
    }),
    { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } }
  );
  const imageBlob = () => new Blob([
    '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">' +
    '<rect width="160" height="160" fill="#1b1b1b"/>' +
    '<circle cx="80" cy="72" r="38" fill="#d14d5b"/>' +
    '<rect x="44" y="110" width="72" height="28" rx="6" fill="#e8d7b5"/>' +
    '</svg>'
  ], { type: 'image/svg+xml' });
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : String(input?.url || input);
    const method = String(init?.method || 'GET').toUpperCase();
    let bodyText = '';
    if (typeof init?.body === 'string') bodyText = init.body;
    else if (init?.body instanceof FormData) bodyText = '[FormData]';
    window.__auroraProbe.calls.push({ url, method, bodyText: bodyText.slice(0, 2000) });

    if (url.includes('/system_stats')) return json({ system: {}, devices: [] });
    if (url.includes('/api/comfyui/status')) return json({ ok: true, running: true });
    if (url.includes('/api/comfyui/start')) return json({ ok: true, ready: true });
    if (url.includes('/object_info/UNETLoader')) {
      return json({ UNETLoader: { input: { required: { unet_name: [[
        'flux1-dev-kontext_fp8_scaled.safetensors',
        'flux1-dev-fp8.safetensors'
      ]] } } } });
    }
    if (url.includes('/upload/image')) {
      window.__auroraProbe.uploads += 1;
      return json({ name: 'probe_reference.png', subfolder: '' });
    }
    if (url.includes('/free')) {
      window.__auroraProbe.frees += 1;
      return json({ ok: true });
    }
    if (url.includes('/interrupt')) {
      window.__auroraProbe.interrupts += 1;
      return json({ ok: true });
    }
    if (url.includes('/api/generate') || url.includes('/api/ollama/generate') || url.includes('/proxy/ollama/api/generate')) {
      const lower = bodyText.toLowerCase();
      if (lower.includes('appearance:')) {
        return ndjson('Purple rabbit-like cartoon humanoid, long upright ears, yellow grin and eyes, pink overalls, yellow gloves, slim friendly pose.');
      }
      if (lower.includes('translate') || lower.includes('instruction-based image editor')) {
        return ndjson('Add the named purple cartoon companion as a friendly friend, integrated in the same photo, with one hand on the shoulder.');
      }
      return ndjson('');
    }
    if (url.endsWith('/prompt') || url.includes('/prompt')) {
      let parsed = null;
      try { parsed = JSON.parse(bodyText || '{}'); } catch {}
      window.__auroraProbe.workflows.push(parsed?.prompt || parsed || {});
      return json({ prompt_id: 'probe-1' });
    }
    if (url.includes('/history/probe-1')) {
      return json({ 'probe-1': { outputs: { '13': { images: [{ filename: 'probe_result.svg', subfolder: '' }] } } } });
    }
    if (url.includes('/view?') || url.includes('/image?')) {
      return new Response(imageBlob(), { status: 200, headers: { 'Content-Type': 'image/svg+xml' } });
    }
    return originalFetch(input, init);
  };
  return true;
})()
`

const helpers = `
(() => {
  window.__auroraProbeHelpers = {
    dismissAdminModal() {
      const target = [...document.querySelectorAll('button')]
        .find((button) => /continuer sans admin/i.test(button.textContent || ''));
      if (target) target.click();
      return Boolean(target);
    },
    clickImageModule() {
      const target = [...document.querySelectorAll('button, a, [role="button"]')]
        .find((el) => (el.textContent || '').replace(/\\s+/g, ' ').toLowerCase().includes('image'));
      if (target) target.click();
      return { clicked: Boolean(target), text: target?.textContent || '' };
    },
    setPrompt(value) {
      const el = [...document.querySelectorAll('textarea, input[type="text"]')]
        .find((node) => /prompt|decris|décris|Ex:/i.test(node.placeholder || '') || node.tagName === 'TEXTAREA');
      if (!el) throw new Error('prompt input not found');
      const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      setter.call(el, value);
      el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
      return el.value;
    },
    uploadReference() {
      const input = document.querySelector('input[type="file"][accept*="image"]');
      if (!input) throw new Error('image file input not found');
      const blob = new Blob([
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><rect width="96" height="96" fill="#e8d7b5"/><circle cx="48" cy="40" r="22" fill="#c96"/></svg>'
      ], { type: 'image/svg+xml' });
      const file = new File([blob], 'probe_reference.svg', { type: 'image/svg+xml' });
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    },
    clickGenerate(count = 1) {
      const buttons = [...document.querySelectorAll('button')];
      const target = buttons.find((button) => /GÃ©nÃ©rer|Generer|TIRER/i.test(button.textContent || '') && !button.disabled);
      const fallback = target || buttons.find((button) => /g.n.rer|generer|generate|tirer/i.test(button.textContent || '') && !button.disabled);
      if (!fallback) throw new Error('generate button not found');
      for (let i = 0; i < count; i += 1) fallback.click();
      return true;
    },
    clickGenerateTwice() {
      const buttons = [...document.querySelectorAll('button')];
      const target = buttons.find((button) => /Générer|Generer|TIRER/i.test(button.textContent || '') && !button.disabled);
      const fallback = target || buttons.find((button) => /g.n.rer|generer|generate|tirer/i.test(button.textContent || '') && !button.disabled);
      if (!fallback) throw new Error('generate button not found');
      fallback.click();
      fallback.click();
      return true;
    },
    bodyLines() {
      return (document.body.innerText || '').split('\\n').map((line) => line.trim()).filter(Boolean);
    },
    summary() {
      const workflows = window.__auroraProbe.workflows || [];
      const workflowText = JSON.stringify(workflows[0] || {});
      const workflowTexts = workflows.map((workflow) => JSON.stringify(workflow || {}));
      return {
        title: document.title,
        calls: window.__auroraProbe.calls.length,
        queueCount: workflows.length,
        uploadCount: window.__auroraProbe.uploads,
        freeCount: window.__auroraProbe.frees,
        interruptCount: window.__auroraProbe.interrupts,
        hasKontextNodes: workflowText.includes('FluxKontextImageScale') && workflowText.includes('ReferenceLatent'),
        hasHumanContract: workflowText.includes('HUMAN PHOTO PRESERVATION'),
        hasCharacterContract: workflowText.includes('ADDED CHARACTER / ENTITY INTEGRATION'),
        hasSocialContract: workflowText.includes('SOCIAL / EMOTIONAL INTERACTION'),
        hasAppearanceClause: workflowText.includes('Purple rabbit-like cartoon humanoid'),
        hasHandOnShoulder: /hand on the shoulder|main sur/i.test(workflowText),
        workflowChecks: workflowTexts.map((text, index) => ({
          index,
          hasKontextNodes: text.includes('FluxKontextImageScale') && text.includes('ReferenceLatent'),
          hasHumanContract: text.includes('HUMAN PHOTO PRESERVATION'),
          hasCharacterContract: text.includes('ADDED CHARACTER / ENTITY INTEGRATION'),
          hasSocialContract: text.includes('SOCIAL / EMOTIONAL INTERACTION'),
          hasBackgroundContract: text.includes('DECOR / BACKGROUND CHANGE'),
          hasOutfitContract: text.includes('OUTFIT / COLOR EDIT'),
          hasPoseContract: text.includes('POSE / COMPOSITION EDIT'),
          hasRemovalContract: text.includes('REMOVAL / REPLACEMENT EDIT'),
          hasTextContract: text.includes('texte ou logo') || text.includes('reecrire ou ajouter le texte') || text.includes('Render the requested text with crisp correct letters'),
          hasAppearanceClause: text.includes('Purple rabbit-like cartoon humanoid'),
          hasHandOnShoulder: /hand on the shoulder|main sur/i.test(text),
          hasNoSingleSubjectConflict: !/must contain exactly one visible person/i.test(text),
          hasNoPreservationAsRemoval: !(
            /sans\s+(?:changer|modifier)/i.test(text)
            && text.includes('REMOVAL / REPLACEMENT EDIT')
            && !/\b(enleve|retire|supprime|efface|remplace|remove|replace|delete|erase)\b/i.test(text)
          ),
        })),
        lockStillSet: Boolean(localStorage.getItem('aurora.imageGenerationLock.v1')),
        previewText: this.bodyLines().filter((line) => /ajout|Kontext|img2img|denoise|continuite|style photo|rendu|Prêt|Pret/i.test(line)).slice(-16),
      };
    },
  };
  return true;
})()
`

async function main() {
  const created = await fetch(`${DEBUG_URL}/json/new?${encodeURIComponent(APP_URL)}`, { method: 'PUT' })
    .then((r) => r.json())
    .catch(() => null)
  const c = await connectPage(APP_MATCH, created?.id || '')
  try {
    const href = await c.eval('location.href').catch(() => '')
    if (!String(href).startsWith(APP_URL)) {
      await c.send('Page.enable').catch(() => {})
      await c.send('Page.navigate', { url: APP_URL }).catch(() => {})
    }
    await waitFor(c, `(() => { try { return location.href.startsWith(${JSON.stringify(APP_URL)}) } catch { return false } })()`, 20000)
    await waitFor(c, 'document.readyState === "complete" || document.readyState === "interactive"', 20000)
    await waitFor(c, 'Boolean(document.body && document.body.innerText.length > 100)', 20000)
    await c.eval('try { localStorage.removeItem("aurora.imageGenerationLock.v1"); localStorage.removeItem("aurora.pendingComfyPrompt.v1"); } catch {}')
    await c.eval(installFetchMocks)
    await c.eval(helpers)
    await c.eval('window.__auroraProbeHelpers.dismissAdminModal()')
    await c.eval('window.__auroraProbeHelpers.clickImageModule()')
    await waitFor(c, 'Boolean(document.querySelector("input[type=file][accept*=image]"))', 10000)

    const previewPrompts = [
      'sur la photo ajoute le personnage Kora de Nebula comme une amie avec une main sur l epaule, meme lumiere et meme perspective',
      'change le decor en cirque colore avec lumiere de scene et perspective coherente',
      'change la tenue en tee shirt rouge et short noir sans changer le corps',
      'change la pose pour etre assise sur le sable, cadrage stable',
      'enleve la couronne puis remplace le fond par une plage',
      'ajoute une couronne doree sans modifier le visage',
      'transforme la photo en pixel art propre mais garde la composition',
      'ecris AURORA sur le panneau en gardant la personne identique',
    ]
    const previews = []
    for (const prompt of previewPrompts) {
      await c.eval(`window.__auroraProbeHelpers.setPrompt(${JSON.stringify(prompt)})`)
      await sleep(250)
      previews.push({
        prompt,
        lines: await c.eval('window.__auroraProbeHelpers.bodyLines().filter((line) => /ajout|Kontext|img2img|denoise|style photo|retirer|decor|pose|tenue/i.test(line)).slice(-10)'),
      })
    }

    await c.setFiles('input[type="file"][accept*="image"]', [REF_FILE])
    await c.eval('document.querySelector("input[type=\\"file\\"][accept*=image]")?.dispatchEvent(new Event("change", { bubbles: true }))')
    await waitFor(c, 'window.__auroraProbe.uploads >= 1', 10000)
    const generationPrompts = [
      'sur la photo ajoute le personnage Kora de Nebula comme une amie avec une main sur l epaule, meme lumiere et meme perspective',
      'change le decor en cirque colore avec lumiere de scene et perspective coherente',
      'change la tenue en tee shirt rouge et short noir sans changer le corps',
      'change la pose pour etre assise sur le sable, cadrage stable',
      'enleve la couronne puis remplace le fond par une plage',
      'ajoute une couronne doree sans modifier le visage',
      'transforme la photo en pixel art propre mais garde la composition',
      'ecris AURORA sur le panneau en gardant la personne identique',
    ]
    for (const [index, prompt] of generationPrompts.entries()) {
      await c.eval(`window.__auroraProbeHelpers.setPrompt(${JSON.stringify(prompt)})`)
      await sleep(150)
      await c.eval(`window.__auroraProbeHelpers.clickGenerate(${index === 0 ? 2 : 1})`)
      await waitFor(c, `window.__auroraProbe.workflows.length >= ${index + 1}`, 15000)
      await waitFor(c, '!localStorage.getItem("aurora.imageGenerationLock.v1")', 15000)
      await sleep(150)
    }
    const summary = await c.eval('window.__auroraProbeHelpers.summary()')
    console.log(JSON.stringify({ previews, generationPrompts, summary }, null, 2))
  } finally {
    c.close()
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
