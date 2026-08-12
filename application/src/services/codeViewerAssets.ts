// Habillage partage des pages viewer (page autonome par run ET hub).
// Extrait pour que le hub et le viewer autonome parlent la meme langue visuelle
// sans dupliquer 60 lignes de CSS.

export const CODE_VIEWER_STYLE = `
*{box-sizing:border-box}
body{margin:0;background:#0d1117;color:#c9d1d9;font:13px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;height:100vh;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:.75rem;padding:.55rem .9rem;background:#0a0f14;border-bottom:1px solid #1c2128;flex:0 0 auto}
header b{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:#e6edf3}
header span{font-size:11px;color:#7d8590}
header .grow{flex:1}
button{font:inherit;font-size:11px;color:#c9d1d9;background:#1c2128;border:1px solid #30363d;border-radius:6px;padding:.25rem .6rem;cursor:pointer}
button:hover{background:#262c34}
button[aria-pressed=true]{background:#1f6feb33;border-color:#1f6feb;color:#cae2ff}
main{flex:1;display:flex;min-height:0}
#tree{width:19rem;flex:0 0 auto;overflow:auto;background:#0b1015;border-right:1px solid #1c2128;padding:.4rem 0}
#tree .row{display:flex;align-items:center;gap:.4rem;padding:.15rem .6rem;cursor:pointer;white-space:nowrap}
#tree .row:hover{background:#161b22}
#tree .row.sel{background:#1f6feb26;color:#cae2ff}
#tree .row .sz{margin-left:auto;font-size:10px;color:#6e7681;font-variant-numeric:tabular-nums}
#tree .dir{color:#e3b341}
#tree .file{color:#8b949e}
#stage{flex:1;min-width:0;display:flex;flex-direction:column}
#bar{display:flex;align-items:center;gap:.5rem;padding:.35rem .7rem;border-bottom:1px solid #1c2128;background:#0a0f14;font-size:11px;color:#7d8590}
#render{flex:1;border:0;background:#fff;width:100%}
#source{flex:1;overflow:auto;margin:0;padding:1rem;background:#0d1117;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre;tab-size:2}
.hidden{display:none!important}
.empty{padding:2rem;color:#7d8590}
@media (max-width:820px){main{flex-direction:column}#tree{width:100%;max-height:38vh;border-right:0;border-bottom:1px solid #1c2128}}
`

export function escapeViewerHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Un projet contient presque toujours `</script>`. Sans echappement, la balise
 * du projet fermerait le bloc JSON de la page et le viewer afficherait sa
 * propre charge utile en texte brut (constate en direct).
 */
export function embedViewerJson(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}
