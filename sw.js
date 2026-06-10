/*
 * Service Worker — 讓網站可「加入主畫面」當 App、離線也能看最後一次盤後資料。
 * 快取策略:
 *   - App 殼層(HTML/CSS/JS/圖示):cache-first + 背景更新(開頁秒開,新版下次生效)
 *   - data/*.json:network-first(永遠先拿最新),離線才退回快取
 * 改版時把 VER 加一,舊快取會在 activate 時清掉。
 */
const VER = "ct-v3";
const SHELL = [
  "./", "index.html", "manifest.webmanifest",
  "assets/style.css",
  "assets/js/01-core.js", "assets/js/02-components.js", "assets/js/03-views.js",
  "assets/js/04-futures.js", "assets/js/05-stealth-short-watch.js", "assets/js/99-boot.js",
  "assets/icons/icon-192.png", "assets/icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VER).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== VER).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // 跨網域(Google Fonts、期交所 enrich)不攔,直連
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  if (url.pathname.includes("/data/")) {
    // 資料:network-first。寫入快取時用去掉 ?_=cache-buster 的路徑當 key,離線才對得到
    e.respondWith(
      fetch(e.request).then((r) => {
        if (r.ok) {
          const copy = r.clone();
          caches.open(VER).then((c) => c.put(url.pathname, copy));
        }
        return r;
      }).catch(() => caches.match(url.pathname))
    );
  } else {
    // 殼層:cache-first + 背景更新。
    // ⚠️ 快取 key 一律用去 query 的 pathname:殼層請求帶 ?v= 版本參數,若用原始
    //    Request 當 key,會和 install 精快取的無 query 條目並存,ignoreSearch 永遠
    //    先比中舊條目 → 殼層永遠 stale。統一 key 才能讓背景更新真的生效。
    e.respondWith(
      caches.match(url.pathname).then((hit) => {
        const net = fetch(e.request).then((r) => {
          if (r.ok) {
            const copy = r.clone();
            caches.open(VER).then((c) => c.put(url.pathname, copy));
          }
          return r;
        }).catch(() => hit);
        return hit || net;
      })
    );
  }
});
