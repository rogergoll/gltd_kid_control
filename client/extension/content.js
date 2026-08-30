// GLTD Kid Control — remodela e bloqueia conteúdo no YouTube.
// Busca a lista de bloqueios do daemon local (http://127.0.0.1:8877/lists),
// bloqueia canais/vídeos e redireciona para a página de bloqueio.

const LOCAL = "http://127.0.0.1:8877";
const BLOCKED_TERMS = [
  "namoro", "namorada", "namorado", "paquera", "crush",
  "lgbt", "gay", "trans", "gênero", "genero", "sexualidade",
  "onlyfans", "+18", "sensual",
];

let blocked = { channels: [], videos: [], domains: [], filters: [] };
let paused = false;
let lastRedirect = "";

async function refreshLists() {
  try {
    const r = await fetch(LOCAL + "/lists");
    if (r.ok) {
      const data = await r.json();
      blocked = data;
      paused = !!data.paused;
    }
  } catch (e) { /* servidor local indisponível */ }
}

function norm(s) { return (s || "").toLowerCase().trim(); }

function videoIdFromUrl(url) {
  try { return new URL(url).searchParams.get("v") || ""; } catch (e) { return ""; }
}

function getChannelInfo() {
  const ownerLink = document.querySelector(
    '#owner a[href^="/@"], ytd-video-owner-renderer a[href^="/@"], #channel-name a, ytd-channel-name a'
  );
  const nameEl = document.querySelector(
    '#owner #channel-name a, ytd-video-owner-renderer #channel-name a, #channel-name #text, #owner #text'
  );
  const name = nameEl ? nameEl.textContent.trim() : "";
  const href = ownerLink ? ownerLink.getAttribute("href") || "" : "";
  return { name, handle: href.replace("/@", "").split("/")[0] };
}

function channelBlocked(ch) {
  const n = norm(ch.name), h = norm(ch.handle);
  if (!n && !h) return false;
  return blocked.channels.some(c =>
    (c.handle && c.handle === h) || (c.name && n && c.name === n) ||
    (c.name && n && n.includes(c.name)));
}

function textBlocked(text) {
  const t = norm(text);
  if (!t) return false;
  if (BLOCKED_TERMS.some(term => t.includes(term))) return true;
  return blocked.filters.some(f => f && t.includes(f));
}

function urlBlocked(url) {
  try {
    const u = new URL(url);
    const id = u.searchParams.get("v") || "";
    if (id && blocked.videos.some(v => videoIdFromUrl(v) === id)) return true;
    if (blocked.videos.some(v => v === url || v === u.href)) return true;
    const host = u.hostname.toLowerCase();
    if (blocked.domains.some(d => d && host.includes(d))) return true;
  } catch (e) { /* ignore */ }
  return false;
}

function redirectIfBlocked() {
  if (paused) return;
  const url = location.href;
  if (url.includes("youtube.com/watch")) {
    const id = videoIdFromUrl(url);
    if (id && blocked.videos.some(v => videoIdFromUrl(v) === id)) {
      go(url); return;
    }
    const ch = getChannelInfo();
    if (channelBlocked(ch)) {
      go(url); return;
    }
    const title = (document.querySelector('meta[name="title"], title') || {}).content || document.title;
    if (textBlocked(title)) {
      go(url); return;
    }
  }
}

function go(url) {
  const target = LOCAL + "/blocked?url=" + encodeURIComponent(url);
  if (lastRedirect === target) return;
  lastRedirect = target;
  // reporta a tentativa bloqueada
  try { fetch(LOCAL + "/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, ts: new Date().toISOString() }) }); } catch (e) {}
  location.replace(target);
}

function hide(el) {
  if (el) { el.style.display = "none"; el.setAttribute("data-gld-hidden", "1"); }
}

function clean() {
  if (paused) return;
  document.querySelectorAll(
    "ytd-shorts, [is-shorts], ytd-shorts-shelf-renderer, ytd-rich-shelf-renderer[is-shorts], ytd-reel-shelf-renderer, a[title='Shorts']"
  ).forEach(hide);

  document.querySelectorAll(
    "ytd-rich-shelf-renderer, ytd-horizontal-card-list-renderer, ytd-watch-next-secondary-results-renderer"
  ).forEach(hide);

  document.querySelectorAll(
    "ytd-rich-item-renderer, ytd-video-renderer, ytd-grid-video-renderer, ytd-compact-video-renderer"
  ).forEach((el) => {
    const title = el.querySelector("#video-title, a#video-title");
    const chan = el.querySelector("ytd-channel-name a, #channel-name #text, .ytd-channel-name");
    const t = (title ? title.textContent : "") + " " + (chan ? chan.textContent : "");
    if (textBlocked(t)) { hide(el); return; }
    if (chan) {
      const n = norm(chan.textContent);
      if (blocked.channels.some(c => (c.name && n && n.includes(c.name)))) { hide(el); return; }
    }
    const link = title ? title.getAttribute("href") : "";
    if (link && urlBlocked(link)) { hide(el); }
  });
}

function watch() {
  clean();
  redirectIfBlocked();
  const observer = new MutationObserver(() => { clean(); redirectIfBlocked(); });
  observer.observe(document.body, { childList: true, subtree: true });
}

async function main() {
  await refreshLists();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watch);
  } else {
    watch();
  }
  // atualiza a lista a cada 15s (novos bloqueios no servidor)
  setInterval(refreshLists, 15000);
}

main();
