export const FOLLOWUP_LABELS: Record<string, string> = {
  increment: 'Modification du projet en cours',
  pivot_platform: 'Changement de stack (même concept)',
  pivot_feature: 'Évolution majeure du projet',
  fresh_start: 'Nouveau projet',
  clarify_only: 'Clarification',
}

// Heuristique simple pour deviner le langage du streamOutput
// avant de le passer à Prism. Le system prompt cadre TS/React par
// défaut, donc 'typescript' est le bon fallback.
export function detectStreamLanguage(prompt: string, output: string): string {
  const p = prompt.toLowerCase()
  if (/\bpython\b|\.py\b|django|flask|pytorch/.test(p)) return 'python'
  if (/\brust\b|\.rs\b|cargo/.test(p)) return 'rust'
  if (/\bgo(lang)?\b|\.go\b/.test(p)) return 'go'
  if (/\bjava\b|\.java\b|spring/.test(p)) return 'java'
  if (/\bc\+\+\b|cpp|\.cpp\b/.test(p)) return 'cpp'
  if (/\bjavascript\b|\.js\b/.test(p) && !/typescript|\.ts/.test(p)) return 'javascript'
  if (/\bsql\b|select.*from/.test(p)) return 'sql'
  if (/\bbash\b|shell|\.sh\b/.test(p)) return 'bash'
  if (/\bcss\b|\.css\b|tailwind/.test(p)) return 'css'
  if (/\bhtml\b|\.html\b/.test(p)) return 'markup'
  if (/\byaml\b|\.ya?ml\b/.test(p)) return 'yaml'
  if (/\bjson\b|\.json\b/.test(p)) return 'json'
  if (/^\s*<(html|!DOCTYPE)/i.test(output)) return 'markup'
  return 'typescript'
}

export const GREEN = 'oklch(0.72 0.12 145)'
export const RED = 'oklch(0.55 0.18 25)'

export function instrumentPreviewHtml(html: string): string {
  const script = `<script>
(function(){
  var send = function(payload) {
    try { window.parent.postMessage(Object.assign({ source: 'aurora-code-preview' }, payload), '*'); } catch (_) {}
  };
  var stringify = function(value) {
    try {
      if (value && value.stack) return String(value.stack);
      if (value && value.message) return String(value.message);
      if (typeof value === 'string') return value;
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  };
  var reportReady = function() {
    try {
      var body = document.body;
      var text = body && body.innerText ? body.innerText.trim() : '';
      send({
        type: 'ready',
        bodyTextLen: text.length,
        nodeCount: body ? body.querySelectorAll('*').length : 0,
        canvasCount: body ? body.querySelectorAll('canvas').length : 0,
        imageCount: body ? body.querySelectorAll('img').length : 0
      });
    } catch (err) {
      send({ type: 'error', message: stringify(err) });
    }
  };
  window.addEventListener('error', function(event) {
    send({
      type: 'error',
      message: event.message || stringify(event.error) || 'Runtime error',
      filename: event.filename || '',
      lineno: event.lineno || 0,
      colno: event.colno || 0
    });
  });
  window.addEventListener('unhandledrejection', function(event) {
    send({ type: 'error', message: stringify(event.reason) || 'Unhandled promise rejection' });
  });
  var originalError = console.error;
  console.error = function() {
    send({ type: 'console', level: 'error', message: Array.prototype.map.call(arguments, stringify).join(' ') });
    return originalError.apply(console, arguments);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ setTimeout(reportReady, 80); }, { once: true });
  } else {
    setTimeout(reportReady, 80);
  }
  window.addEventListener('load', function(){ setTimeout(reportReady, 160); }, { once: true });
})();
<\/script>`

  if (/<head[\s>]/i.test(html)) {
    return html.replace(/<head([^>]*)>/i, `<head$1>${script}`)
  }
  if (/<html[\s>]/i.test(html)) {
    return html.replace(/<html([^>]*)>/i, `<html$1>${script}`)
  }
  return `${script}${html}`
}
