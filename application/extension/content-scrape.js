/**
 * Captures authenticated ENT pages for Aurora-Connect.
 *
 * The service worker calls this script after login to verify the session,
 * collect readable text, list-like containers, page signals, and downloadable
 * course documents. It also exposes frame-safe helpers so iframes can be
 * scraped when an ENT splits its UI across frames.
 */
(function () {
  'use strict'
  if (!chrome.runtime || !chrome.runtime.onMessage) return

  function detectAuthSuccess(authMarkers) {
    // 1. The URL should no longer look like a login page.
    const url = window.location.href.toLowerCase()
    const looksLogin = /\/login|\/auth|\/connexion|\/sign[\s-]?in/i.test(url)
    // 2. Pas d'error markers.
    const errSelectors = [
      '.error-login', '.alert-danger', '.error-msg',
      '[role="alert"][class*="error" i]',
    ]
    let errFound = false
    for (const s of errSelectors) {
      try {
        const el = document.querySelector(s)
        if (el && el.offsetParent !== null) {
          const txt = (el.textContent || '').toLowerCase()
          if (/incorrect|invalide|erreur|wrong|failed/i.test(txt)) {
            errFound = true
            break
          }
        }
      } catch { /* noop */ }
    }
    // 3. Expected authenticated-page markers.
    let markersFound = 0
    if (Array.isArray(authMarkers)) {
      for (const sel of authMarkers) {
        try { if (document.querySelector(sel)) markersFound++ } catch { /* noop */ }
      }
    }
    const score = authMarkers && authMarkers.length > 0
      ? markersFound / authMarkers.length
      : (looksLogin ? 0 : 0.5)
    return {
      ok: !errFound && !looksLogin && score >= 0.3,
      url, looksLogin, errFound, markersFound,
      authMarkersTotal: authMarkers?.length || 0,
      score,
    }
  }

  // v82l6 â€” page typology purely topological. Same logic as analyze_page in
  // background.js, ported here so the Pronote/ENT scrape path benefits from
  // pageType + signals too. The bridge `/api/ent/analyze-dom` (or any LLM
  // consumer) can use these to weight extraction strategies â€” eg listing +
  // iframeCount>0 â†’ trust iframeTexts more than body text.
  //
  // v82lx â€” social_feed detection. Listings of *cards* (LinkedIn posts,
  // Twitter timeline, Facebook feed, GitHub Discussions) share four
  // topological signatures :
  //   1. repeating cards (>=5 of same tag at the same depth) â€” already via
  //      listLikeCount.
  //   2. avatars : <img> nested inside a card-shaped wrapper, often inside
  //      role=link or with width<=80px square aspect.
  //   3. relative timestamps in card text ("il y a 3 h", "5 min ago",
  //      "2j", "yesterday"). Detected with a locale-tolerant regex on the
  //      first ~3 KB of card-region innerText.
  //   4. reaction/like buttons (aria-label containing "aim"/"ike"/"react",
  //      case-insensitive). The most stable cross-site signal â€” every social
  //      platform uses an aria-label with one of these stems.
  // ZERO selectors hardcoded per site. The LLM planner reads
  // pageType.social_feed and adapts the scrape strategy : "social_feed â†’
  // card-iteration mode â†’ one structured item per card".
  function detectSocialFeedSignals(rootDoc, listLikeCount) {
    try {
      const text = (rootDoc.body?.innerText || '').slice(0, 6000)
      // Avatars : small square <img> inside an <a>/role=link OR inside a
      // header-like ancestor. Topological â€” no class names.
      let avatarHits = 0
      const imgs = Array.from(rootDoc.querySelectorAll('img[src]')).slice(0, 100)
      for (const im of imgs) {
        const w = im.naturalWidth || im.width || 0
        const h = im.naturalHeight || im.height || 0
        const square = w > 0 && h > 0 && Math.abs(w - h) <= 8 && w <= 96
        if (!square) continue
        // Walk up max 4 ancestors looking for a link or header role.
        let p = im.parentElement
        for (let d = 0; d < 4 && p; d++, p = p.parentElement) {
          const tag = p.tagName
          const role = (p.getAttribute && p.getAttribute('role')) || ''
          if (tag === 'A' || role === 'link' || tag === 'HEADER') {
            avatarHits++
            break
          }
        }
      }
      // Relative timestamps. FR/EN/DE/ES tolerant. Locale agnostic â€” pure
      // pattern detection. Examples : "il y a 3 h", "5 min ago", "2j",
      // "yesterday", "vor 2 std", "hace 5 min".
      const tsRe = /(?:il y a\s+\d+|\d+\s*(?:min|mn|h|j|d|w|m|s|sec|hr|hrs|hour|hours|day|days|week|weeks|month|months)\b\s*(?:ago|hier)?|vor\s+\d+\s*(?:min|std|tag|tagen)|hace\s+\d+\s*(?:min|h|d[íi]a)|yesterday|hier|aujourd['’ ]?hui|today|just now|à l['’ ]instant)/i
      const hasTimestamps = tsRe.test(text)
      // Reaction buttons. The aria-label is the most stable cross-site cue.
      // We accept "aim" (j'aime, aimer), "ike" (like), "react" (react/reaction),
      // "pplaud" (applaudir, applaud â€” LinkedIn).
      let reactionButtons = 0
      const buttons = Array.from(rootDoc.querySelectorAll('button[aria-label], [role=button][aria-label]')).slice(0, 200)
      const reactRe = /aim|ike|react|pplaud|recommend|partage|share|comment|comentar|kommentar/i
      for (const b of buttons) {
        const lbl = b.getAttribute('aria-label') || ''
        if (lbl && reactRe.test(lbl)) reactionButtons++
      }
      const repeatingCards = listLikeCount >= 5
      // social_feed verdict : need at least 3 of the 4 signals. A pure
      // listing of <li> bullets without avatars/timestamps/reactions stays
      // pageType.listing â€” only feeds-of-cards graduate.
      const score = (repeatingCards ? 1 : 0) + (avatarHits >= 2 ? 1 : 0)
        + (hasTimestamps ? 1 : 0) + (reactionButtons >= 2 ? 1 : 0)
      return {
        socialFeed: score >= 3,
        socialFeedScore: score,
        avatarHits,
        hasTimestamps,
        reactionButtons,
        repeatingCardCount: listLikeCount,
      }
    } catch {
      return {
        socialFeed: false, socialFeedScore: 0,
        avatarHits: 0, hasTimestamps: false, reactionButtons: 0,
        repeatingCardCount: 0,
      }
    }
  }

  // v82n0 â€” article quality + paywall detection. Pure topology (zero hardcoded
  // sites). The planner uses pageType.article_quality to decide :
  //   - 'rich'    â†’ text scrape is sufficient, plan a simple analyze + reply
  //   - 'thin'    â†’ text alone won't synthesise much, suggest screenshot+vision
  //   - 'paywall' â†’ hint user to use Bypass Paywalls Clean / archive.is
  //   - 'unknown' â†’ not an article (no article tag) or signals ambiguous
  //
  // Gates :
  //   rich    : <article> tag + text >1500 chars + >=2 long <p> + has h1/h2
  //   thin    : <article> tag but text <800 chars OR teaser-only (paywall sig)
  //   paywall : article tag present derriere AND overlay covers >60% screen
  //             height AND overlay innerText contains multilingual auth/sub
  //             keyword ("abonn"/"subscri"/"premium"/"log in"/"sign in"/
  //             "register")
  //   unknown : reste
  //
  // Multilingual auth keywords : FR (abonn-er, abonn-ement, connect-er,
  // inscri-re), EN (subscri-be, log in, sign in, register, premium), DE
  // (anmel-den, abonn-ieren), ES (suscri-bir, registr-ar). We use stems so
  // we don't need exhaustive forms.
  function detectArticleQuality(rootDoc, articleTag, text) {
    try {
      if (!articleTag) return 'unknown'
      const longParagraphs = Array.from(rootDoc.querySelectorAll('article p, main p, [role=main] p, body p'))
        .filter((p) => (p.textContent || '').trim().length > 100)
        .length
      const hasHeading = !!rootDoc.querySelector('article h1, article h2, main h1, main h2, h1, h2')
      // Paywall : look for any element whose getBoundingClientRect covers a
      // large fraction of the viewport AND its innerText carries auth/sub
      // signature words. Limit scan to top 250 elements to keep it cheap.
      const authStems = /abonn|subscri|premium|log\s*in|sign\s*in|register|inscri|connect|anmeld|suscri|registr/i
      let paywall = false
      try {
        const vw = rootDoc.defaultView || window
        const viewH = vw?.innerHeight || rootDoc.documentElement?.clientHeight || 0
        if (viewH > 0) {
          // Candidates : fixed/absolute overlays. We scan all elements with
          // role=dialog OR position-affecting containers heuristically.
          const candidates = Array.from(rootDoc.querySelectorAll('[role=dialog], aside, dialog, div, section'))
            .slice(0, 250)
          for (const el of candidates) {
            try {
              const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null
              if (!rect) continue
              const coverage = rect.height / viewH
              if (coverage < 0.6) continue
              // Avoid matching on the article body itself (must be a discrete
              // overlay-ish element â€” limit text length so we don't pick up
              // the entire main content). Paywall overlays are typically
              // small text (call to action). >2000 chars means it's the
              // article itself, skip.
              const inner = (el.innerText || '').trim()
              if (inner.length === 0 || inner.length > 2000) continue
              if (authStems.test(inner)) {
                paywall = true
                break
              }
            } catch { /* noop */ }
          }
        }
      } catch { /* noop */ }
      if (paywall && text.length < 3000) return 'paywall'
      if (text.length >= 1500 && longParagraphs >= 2 && hasHeading) return 'rich'
      if (text.length < 800) return 'thin'
      return 'unknown'
    } catch {
      return 'unknown'
    }
  }

  // v82n0 â€” listing subtype heuristic. Pure topology (no hardcoded selectors)
  // that classifies a generic listing into 'search_results' | 'product_listing'
  // | 'news_listing' | 'generic'. Threaded into pageType.signals so the planner
  // can offer the LLM a structured-output hint per subtype.
  //
  // Gates (apply only when pageType.listing=true) :
  //   search_results  : listLikeCount >= 8 AND most items have a heading +
  //                     external href + snippet pattern (h-tag + a + p inside)
  //   product_listing : listLikeCount >= 5 AND >=3 items contain a price-like
  //                     pattern in their innerText (currency + digits)
  //   news_listing    : listLikeCount >= 5 AND >=3 items contain a timestamp
  //                     hint (relative or absolute date) + author-like signature
  //   generic         : listing without enough subtype signal
  //
  // Multilingual currencies : â‚¬ $ Â£ Â¥ â‚¹ â‚½ + the literal codes EUR/USD/GBP.
  function detectListingSubtype(rootDoc, listLikeCount) {
    try {
      if (listLikeCount < 5) return 'generic'
      const containers = Array.from(rootDoc.querySelectorAll('main, section, [role=main], body'))
      let bestParent = null
      let bestTag = null
      let bestCount = 0
      for (const c of containers.slice(0, 8)) {
        const counts = {}
        for (const ch of Array.from(c.children)) {
          counts[ch.tagName] = (counts[ch.tagName] || 0) + 1
        }
        for (const k of Object.keys(counts)) {
          if (counts[k] >= 5 && counts[k] > bestCount) {
            bestParent = c
            bestTag = k
            bestCount = counts[k]
          }
        }
      }
      if (!bestParent || !bestTag) return 'generic'
      const items = Array.from(bestParent.children).filter((ch) => ch.tagName === bestTag).slice(0, 30)
      // Patterns
      const priceRe = /[€$£¥₹₽]\s*\d|\d[\d.,]*\s*(?:€|\$|£|¥|EUR|USD|GBP|JPY)/i
      // Timestamps : relative ("3 days ago", "il y a 3h", "5 min") or absolute
      // ("12 mars 2024", "Mar 12, 2024", "2024-03-12")
      const tsRe = /\b\d+\s*(?:min|h|j|d|hour|hours|day|days|week|month|year|ago|hier)\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|fevr|mars|avr|mai|juin|juil|aout|sept|oct|nov|dec)[a-zé]*\.?\s+\d|\d{4}-\d{2}-\d{2}/i
      // Author-like : "By <name>" / "par <name>" / @handle
      const authorRe = /\b(?:by|par|von|de|@)\s+[A-Z][a-zA-ZÀ-ÿ-]+/
      let priceCount = 0, tsCount = 0, authorCount = 0
      // Search-results signature : item has heading-like child AND link AND
      // descriptive text (snippet). Count items matching this triad.
      let searchTriadCount = 0
      for (const it of items) {
        const txt = (it.innerText || '')
        if (priceRe.test(txt)) priceCount++
        const tsHit = tsRe.test(txt)
        if (tsHit) tsCount++
        if (authorRe.test(txt)) authorCount++
        try {
          const heading = it.querySelector('h1,h2,h3,h4,[role=heading]')
          const link = it.querySelector('a[href]')
          // Snippet check : the item has at least 100 chars text beyond its heading.
          const headingText = heading ? (heading.textContent || '').trim().length : 0
          const totalText = txt.trim().length
          const hasSnippet = totalText > headingText + 80
          if (heading && link && hasSnippet) searchTriadCount++
        } catch { /* noop */ }
      }
      // Decide. Order matters : product (price) is the strongest, then news
      // (timestamps + authors), then search (heading+link+snippet >=8 items).
      if (priceCount >= 3) return 'product_listing'
      if (tsCount >= 3 && authorCount >= 2) return 'news_listing'
      if (listLikeCount >= 8 && searchTriadCount >= Math.min(items.length, 6)) {
        return 'search_results'
      }
      return 'generic'
    } catch {
      return 'generic'
    }
  }

  function detectPageTypology(rootDoc, tableCount, iframeCount) {
    try {
      const passwordInputs = rootDoc.querySelectorAll('input[type=password]').length
      const formCount = rootDoc.querySelectorAll('form').length
      const articleTag = !!rootDoc.querySelector('article')
      const videoCount = rootDoc.querySelectorAll('video').length
      const canvasCount = rootDoc.querySelectorAll('canvas').length
      const imgCount = rootDoc.querySelectorAll('img[src]').length
      // Sibling-tag-frequency listing detection : in any direct container
      // (main, section, [role=main], body), if 5+ children share the same
      // tag, the page is listing-like. listLikeCount = max repeats found.
      const containers = Array.from(rootDoc.querySelectorAll('main, section, [role=main], body'))
      let listLike = 0
      for (const c of containers.slice(0, 8)) {
        const counts = {}
        for (const child of Array.from(c.children)) {
          counts[child.tagName] = (counts[child.tagName] || 0) + 1
        }
        for (const k of Object.keys(counts)) {
          if (counts[k] >= 5) listLike = Math.max(listLike, counts[k])
        }
      }
      const text = (rootDoc.body?.innerText || '')
      // v82lx â€” social_feed signals (avatars, timestamps, reactions).
      const sf = detectSocialFeedSignals(rootDoc, listLike)
      // v82n0 â€” article quality (rich/thin/paywall/unknown) + listing subtype.
      const articleQuality = detectArticleQuality(rootDoc, articleTag, text)
      const listingSubtype = detectListingSubtype(rootDoc, listLike)
      const pageType = {
        login: passwordInputs >= 1 && formCount >= 1,
        article: articleTag && text.length > 800,
        listing: listLike >= 5 || tableCount >= 1,
        media: videoCount >= 1 || canvasCount >= 1,
        form: formCount >= 1 && passwordInputs === 0,
        dashboard: text.length < 600 && imgCount >= 3,
        social_feed: sf.socialFeed,
        article_quality: articleQuality,
      }
      const signals = {
        passwordInputs, formCount, articleTag, videoCount, canvasCount,
        listLikeCount: listLike,
        tableCount,
        iframeCount,
        avatarHits: sf.avatarHits,
        hasTimestamps: sf.hasTimestamps,
        reactionButtons: sf.reactionButtons,
        socialFeedScore: sf.socialFeedScore,
        repeatingCardCount: sf.repeatingCardCount,
        articleQuality,
        listingSubtype,
      }
      return { pageType, signals }
    } catch {
      return { pageType: {}, signals: {} }
    }
  }

  function extractTextSnapshot() {
    let text = (document.body?.innerText || '').slice(0, 30_000)
    const title = document.title || ''
    const url = window.location.href

    // v82l0 : Pronote (et autres ENT) chargent leur contenu dans des
    // iframes same-origin. body.innerText les rate. On parcourt toutes
    // les iframes accessibles et on concat leur innerText.
    let iframeCountAccessible = 0
    try {
      const iframes = document.querySelectorAll('iframe')
      const parts = []
      for (const f of iframes) {
        try {
          const doc = f.contentDocument || f.contentWindow?.document
          if (!doc?.body) continue
          const inner = (doc.body.innerText || '').slice(0, 20_000)
          if (inner && inner.length > 50) {
            iframeCountAccessible++
            parts.push(`\n\n=== iframe ${f.name || f.id || f.src || '(unnamed)'} ===\n${inner}`)
          }
        } catch {
          // cross-origin iframe â€” pas accessible
        }
      }
      if (parts.length > 0) {
        text = (text + parts.join('')).slice(0, 60_000) // bump to 60KB if iframe content
      }
    } catch { /* noop */ }

    // Conteneurs probables de listings.
    const containers = []
    const sel = [
      'table', 'ul.list', 'ul[class*="liste" i]', 'ul[class*="items" i]',
      'div[ng-repeat]', '[data-testid*="list" i]', '[data-testid*="row" i]',
      '.ligne', '.list-item', '.row', '.card-list',
      // v82l0 Pronote : cellule_X classes (cellule_TravailAFaire, cellule_Note, etc.)
      '[class*="cellule_" i]', '[class*="ligne" i]',
      // Pronote uses div.UnePart structures and tabs
      '.UnePart', '.partie', '.contenu-page', '.GTLContent',
      // Tables & rows in any context
      'tr', 'tbody',
    ]
    for (const s of sel) {
      try {
        const found = document.querySelectorAll(s)
        for (const el of found) {
          if (containers.length >= 30) break
          const html = el.outerHTML.slice(0, 5_000)
          if (html.length > 200) containers.push({ selector: s, html })
        }
      } catch { /* noop */ }
    }
    // v82l0 : same iframe sweep for containers
    try {
      const iframes = document.querySelectorAll('iframe')
      for (const f of iframes) {
        if (containers.length >= 40) break
        try {
          const doc = f.contentDocument || f.contentWindow?.document
          if (!doc?.body) continue
          for (const s of sel) {
            const found = doc.querySelectorAll(s)
            for (const el of found) {
              if (containers.length >= 40) break
              const html = el.outerHTML.slice(0, 5_000)
              if (html.length > 200) containers.push({ selector: `iframe ${s}`, html })
            }
          }
        } catch { /* cross-origin */ }
      }
    } catch { /* noop */ }

    // v82l6 â€” page typology + signals. Computed on the main document ;
    // tableCount counts every <tr>/<tbody>/<table> in the containers list
    // as a proxy for listing density. iframeCount uses the accessible
    // (same-origin) iframes counted above.
    const tableCount = containers.filter((c) =>
      c.selector === 'table' || c.selector === 'tr' || c.selector === 'tbody'
      || c.selector === 'iframe table' || c.selector === 'iframe tr' || c.selector === 'iframe tbody',
    ).length
    const { pageType, signals } = detectPageTypology(document, tableCount, iframeCountAccessible)

    // v82ly â€” when social_feed is detected, stream a focalised cards[]
    // array to the bridge in addition to text/containers. We find the
    // parent container in (main, section, [role=main], body) that
    // maximises the listLike count (i.e. holds the repeating card-shaped
    // children) and slice up to 20 of its children's outerHTML capped at
    // 5_000 chars each. The bridge route extract_structured + mode=
    // card_iteration receives this and can prompt the LLM per-card with
    // focused markup instead of a 60 KB body blob.
    //
    // ZERO selector hardcoded site-specific. We rely on the same
    // topological scan as detectPageTypology â€” sibling-tag-frequency.
    // text/containers stay populated as fallback in case cards extraction
    // misses (eg. listLike was inside an iframe or a deeper nest).
    let cards
    try {
      if (pageType && pageType.social_feed) {
        const cardCandidates = Array.from(document.querySelectorAll('main, section, [role=main], body'))
        let best = null
        let bestCount = 0
        let bestTag = null
        for (const c of cardCandidates.slice(0, 8)) {
          const counts = {}
          for (const child of Array.from(c.children)) {
            counts[child.tagName] = (counts[child.tagName] || 0) + 1
          }
          for (const tag of Object.keys(counts)) {
            if (counts[tag] >= 5 && counts[tag] > bestCount) {
              best = c
              bestCount = counts[tag]
              bestTag = tag
            }
          }
        }
        if (best && bestTag) {
          const out = []
          let idx = 0
          for (const child of Array.from(best.children)) {
            if (out.length >= 20) break
            if (child.tagName !== bestTag) continue
            const html = (child.outerHTML || '').slice(0, 5_000)
            if (html.length < 80) continue
            out.push({ idx, outerHTML: html })
            idx++
          }
          if (out.length > 0) cards = out
        }
      }
    } catch { /* noop â€” cards extraction is best-effort, fall back to text/containers */ }

    return { text, title, url, containers, pageType, signals, cards }
  }

  function extractAttachmentLinks() {
    // Links that look like downloadable school documents.
    const links = []
    const seen = new Set()
    const re = /\.(pdf|docx?|odt|rtf|txt|csv|xlsx?|pptx?|jpg|jpeg|png|webp|zip)(?:[?#].*)?$/i
    const hintRe = /telecharg|télécharg|download|attachment|piece\s*jointe|pi[eè]ce\s*jointe|fichier|document|ressource|corrig|annale|sujet|fiche/i
    function pushFromDoc(rootDoc, scope) {
      const all = Array.from(rootDoc.querySelectorAll('a[href], area[href]'))
      for (const a of all) {
        if (links.length >= 150) break
        const href = a.href
        if (!href || seen.has(href)) continue
        const text = (a.textContent || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim()
        const downloadName = a.getAttribute('download') || ''
        const type = a.getAttribute('type') || ''
        const looksFile = re.test(href) || re.test(downloadName) || /pdf|word|excel|powerpoint|zip|octet-stream/i.test(type)
        const looksAcademic = hintRe.test(href) || hintRe.test(text) || hintRe.test(downloadName)
        if (!looksFile && !looksAcademic) continue
        seen.add(href)
        links.push({
          url: href,
          text: text.slice(0, 200),
          filename: downloadName || undefined,
          download: downloadName || undefined,
          type: type || undefined,
          scope,
        })
      }
    }
    pushFromDoc(document, 'main')
    try {
      for (const f of Array.from(document.querySelectorAll('iframe')).slice(0, 10)) {
        if (links.length >= 150) break
        try {
          const doc = f.contentDocument || f.contentWindow?.document
          if (!doc?.body) continue
          pushFromDoc(doc, `iframe:${f.name || f.id || f.src || 'unnamed'}`)
        } catch { /* cross-origin */ }
      }
    } catch { /* noop */ }
    return links
  }

  function buildScrapePageResponse() {
    const snapshot = extractTextSnapshot()
    const attachments = extractAttachmentLinks()
    return {
      ok: true,
      snapshot,
      attachments,
      hostname: window.location.hostname,
      ts: Date.now(),
      frameUrl: window.location.href,
      frameTitle: document.title,
    }
  }

  window.__auroraVerifyAuth = (authMarkers) => detectAuthSuccess(authMarkers || [])
  window.__auroraScrapePage = () => buildScrapePageResponse()

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === 'aurora-verify-auth') {
      // Wait 1.5s settle (SPAs need time to populate DOM post-auth).
      setTimeout(() => {
        sendResponse(window.__auroraVerifyAuth(msg.authMarkers || []))
      }, 1500)
      return true
    }
    if (msg && msg.type === 'aurora-scrape-page') {
      try {
        sendResponse(buildScrapePageResponse())
      } catch (err) {
        sendResponse({ ok: false, error: String(err) })
      }
      return false
    }
  })
})()

