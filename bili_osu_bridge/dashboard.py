from __future__ import annotations

import logging
from collections.abc import Callable

from aiohttp import web


logger = logging.getLogger(__name__)


_DASHBOARD_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>osu-BiliRequest queue</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d1018;
      --panel: #171b27;
      --line: #2a3041;
      --text: #f3f5fb;
      --muted: #9ba4b8;
      --pink: #ff66aa;
      --blue: #64b5ff;
      --green: #69e39a;
      --yellow: #ffd166;
      --red: #ff758c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 12% 0%, #40203c 0, transparent 28rem),
        radial-gradient(circle at 90% 10%, #123451 0, transparent 30rem),
        var(--bg);
      color: var(--text);
      font: 15px/1.5 "Segoe UI", "Microsoft YaHei", sans-serif;
    }
    main { width: min(1080px, calc(100% - 32px)); margin: 0 auto; padding: 34px 0 60px; }
    header { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
    h1 { margin: 0; font-size: clamp(28px, 5vw, 48px); letter-spacing: -1.5px; }
    h1 span { color: var(--pink); }
    .subtitle, .muted { color: var(--muted); }
    .badge { display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 999px; padding: 8px 13px; background: #111520cc; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--red); box-shadow: 0 0 14px currentColor; }
    .connected .dot { background: var(--green); }
    .grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr); gap: 16px; }
    .panel { background: #171b27e8; border: 1px solid var(--line); border-radius: 18px; padding: 20px; box-shadow: 0 18px 60px #0005; }
    .eyebrow { color: var(--pink); font-weight: 700; text-transform: uppercase; letter-spacing: .12em; font-size: 12px; }
    #current-map { font-size: clamp(19px, 3vw, 28px); font-weight: 700; margin: 8px 0 4px; overflow-wrap: anywhere; }
    .count { font-size: 42px; line-height: 1; font-weight: 800; color: var(--blue); margin: 9px 0 7px; }
    .section-head { display: flex; justify-content: space-between; align-items: center; margin: 28px 2px 12px; }
    h2 { margin: 0; font-size: 20px; }
    #requests { display: grid; gap: 10px; }
    .request { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: center; background: #151925; border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }
    .request-main { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: 12px; align-items: center; min-width: 0; }
    .request-avatar { position: relative; display: grid; place-items: center; width: 46px; height: 46px; border: 2px solid #ffffff70; border-radius: 50%; overflow: hidden; background: linear-gradient(145deg, var(--pink), #7554aa); color: white; font-size: 18px; font-weight: 800; }
    .request-avatar img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .requester { color: var(--pink); font-size: 13px; font-weight: 800; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .request-title { font-weight: 700; overflow-wrap: anywhere; }
    .request-meta { color: var(--muted); font-size: 13px; margin-top: 4px; }
    .tags { display: flex; justify-content: end; flex-wrap: wrap; gap: 7px; }
    .tag { border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; background: #282d3d; color: #d7dceb; }
    .tag.current { background: #163c2b; color: var(--green); }
    .tag.other { background: #3c2d13; color: var(--yellow); }
    .tag.failed { background: #421d28; color: var(--red); }
    .tag.processing { background: #17344c; color: var(--blue); }
    .empty { text-align: center; color: var(--muted); padding: 48px 20px; border: 1px dashed var(--line); border-radius: 14px; }
    .preview-shell { margin-top: 12px; padding: 12px; border: 1px solid var(--line); border-radius: 18px; background-color: #10141e; background-image: linear-gradient(45deg, #171c29 25%, transparent 25%), linear-gradient(-45deg, #171c29 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #171c29 75%), linear-gradient(-45deg, transparent 75%, #171c29 75%); background-size: 24px 24px; background-position: 0 0, 0 12px, 12px -12px, -12px 0; overflow: auto; }
    .preview-shell iframe { display: block; width: 760px; height: 100px; margin: 0 auto; border: 0; background: transparent; transition: height .2s ease; }
    .overlay-tools { display: flex; justify-content: end; align-items: center; flex-wrap: wrap; gap: 8px 12px; }
    .overlay-url { color: #cbd2e2; font: 13px/1.4 Consolas, monospace; }
    .copy-button { appearance: none; border: 1px solid #4c5570; border-radius: 8px; padding: 5px 10px; background: #242a3a; color: var(--text); font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; }
    .copy-button:hover { border-color: var(--pink); color: var(--pink); }
    footer { margin-top: 28px; color: var(--muted); font-size: 12px; text-align: center; }
    @media (max-width: 680px) {
      header { align-items: start; flex-direction: column; }
      .grid { grid-template-columns: 1fr; }
      .request { grid-template-columns: 1fr; }
      .tags { justify-content: start; }
      .preview-shell iframe { margin: 0; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div><h1><span>osu</span>-BiliRequest</h1><div class="subtitle">tosu live queue dashboard</div></div>
    <div id="tosu-badge" class="badge"><i class="dot"></i><span>tosu 连接中</span></div>
  </header>
  <section class="grid">
    <div class="panel">
      <div class="eyebrow">osu! 当前谱面</div>
      <div id="current-map">等待 tosu…</div>
      <div id="game-state" class="muted">—</div>
    </div>
    <div class="panel">
      <div class="eyebrow">活动队列</div>
      <div id="queue-count" class="count">0</div>
      <div class="muted">等待中与处理中</div>
    </div>
  </section>
  <div class="section-head"><h2>点歌队列</h2><span id="last-update" class="muted"></span></div>
  <section id="requests"><div class="empty">还没有点歌记录</div></section>
  <div class="section-head">
    <h2>Overlay</h2>
    <div class="overlay-tools">
      <span class="muted">实际地址：<code id="overlay-url" class="overlay-url">/overlay</code></span>
      <button id="copy-overlay-url" class="copy-button" type="button">复制 URL</button>
      <span class="muted">推荐分辨率：760 × 100</span>
    </div>
  </div>
  <section class="preview-shell"><iframe id="overlay-preview" src="/overlay" title="OBS 点歌 Overlay"></iframe></section>
  <footer>仅监听 http://127.0.0.1 · 页面每秒自动更新</footer>
</main>
<script>
  const labels = {queued: '等待中', processing: '处理中', sent: '已发送', failed: '失败'};
  const requestsNode = document.getElementById('requests');
  const overlayPreview = document.getElementById('overlay-preview');
  const overlayUrl = `${location.origin}/overlay`;
  const copyButton = document.getElementById('copy-overlay-url');
  document.getElementById('overlay-url').textContent = overlayUrl;
  copyButton.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(overlayUrl);
    } catch (_) {
      const field = document.createElement('textarea');
      field.value = overlayUrl;
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.append(field);
      field.select();
      document.execCommand('copy');
      field.remove();
    }
    copyButton.textContent = '已复制';
    setTimeout(() => { copyButton.textContent = '复制 URL'; }, 1500);
  });
  window.addEventListener('message', event => {
    if (
      event.origin === location.origin &&
      event.source === overlayPreview.contentWindow &&
      event.data && event.data.type === 'bili-overlay-height'
    ) {
      const height = Math.min(110, Math.max(20, Number(event.data.height) + 4));
      if (Number.isFinite(height)) overlayPreview.style.height = `${height}px`;
    }
  });

  function tag(text, className = '') {
    const node = document.createElement('span');
    node.className = `tag ${className}`;
    node.textContent = text;
    return node;
  }

  function renderRequests(items) {
    requestsNode.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = '还没有点歌记录';
      requestsNode.append(empty);
      return;
    }
    for (const item of items) {
      const row = document.createElement('article');
      row.className = 'request';
      const main = document.createElement('div');
      main.className = 'request-main';
      const avatar = document.createElement('div');
      avatar.className = 'request-avatar';
      const fallback = document.createElement('span');
      fallback.textContent = Array.from(item.requester || '观众')[0] || '?';
      const avatarImage = document.createElement('img');
      avatarImage.alt = '';
      avatarImage.referrerPolicy = 'no-referrer';
      avatarImage.style.display = item.avatarUrl ? 'block' : 'none';
      if (item.avatarUrl) avatarImage.src = item.avatarUrl;
      avatarImage.addEventListener('error', () => { avatarImage.style.display = 'none'; });
      avatar.append(fallback, avatarImage);
      const body = document.createElement('div');
      const requester = document.createElement('div');
      requester.className = 'requester';
      requester.textContent = item.requester || 'bilibili 观众';
      const title = document.createElement('div');
      title.className = 'request-title';
      title.textContent = item.mapLabel || item.reference;
      const meta = document.createElement('div');
      meta.className = 'request-meta';
      meta.textContent = `${item.reference} · ${new Date(item.createdAt * 1000).toLocaleTimeString()}`;
      body.append(requester, title, meta);
      main.append(avatar, body);

      const tags = document.createElement('div');
      tags.className = 'tags';
      const stateClass = item.state === 'failed' ? 'failed' : item.state === 'processing' ? 'processing' : '';
      tags.append(tag(labels[item.state] || item.state, stateClass));
      if (item.currentMatch === true) tags.append(tag('当前谱面', 'current'));
      else if (item.currentMatch === false) tags.append(tag('非当前谱面', 'other'));
      else tags.append(tag('尚未判断'));
      row.append(main, tags);
      requestsNode.append(row);
    }
  }

  async function refresh() {
    try {
      const response = await fetch('/api/status', {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const badge = document.getElementById('tosu-badge');
      badge.classList.toggle('connected', data.tosu.connected);
      badge.querySelector('span').textContent = !data.tosu.enabled ? 'tosu 已停用' : data.tosu.connected ? 'tosu 已连接' : 'tosu 未连接';
      document.getElementById('current-map').textContent = data.tosu.connected ? data.tosu.beatmapDisplayLabel : (!data.tosu.enabled ? '未启用 tosu 状态同步' : '无法读取 osu! 当前谱面');
      document.getElementById('game-state').textContent = data.tosu.connected ? `状态：${data.tosu.state || '未知'} · Beatmap ${data.tosu.beatmapId || '—'}` : (data.tosu.error || '请确认 tosu 正在运行');
      document.getElementById('queue-count').textContent = data.queueCount;
      document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
      renderRequests(data.requests);
    } catch (error) {
      document.getElementById('last-update').textContent = `页面连接失败：${error.message}`;
    }
  }
  refresh();
  setInterval(refresh, 1000);
</script>
</body>
</html>
"""


_OVERLAY_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>osu-BiliRequest OBS overlay</title>
  <style>
    :root {
      color-scheme: dark;
      --pink: #fb7299;
      --blue: #63c8ff;
      --green: #69e39a;
      --text: #fff;
      --muted: #c3c9d6;
      --panel: rgba(15, 18, 28, .94);
      --line: rgba(255, 255, 255, .15);
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; background: transparent !important; overflow: hidden; }
    body {
      padding: 5px;
      color: var(--text);
      font: 16px/1.3 "Segoe UI", "Microsoft YaHei", sans-serif;
      text-shadow: 0 1px 3px #000b;
    }
    #overlay { width: calc(100vw - 10px); }
    #queue:empty { display: none; }
    .request {
      display: grid;
      grid-template-columns: 64px minmax(0, 1fr);
      gap: 14px;
      align-items: center;
      min-height: 90px;
      padding: 10px 16px 10px 12px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--pink);
      border-radius: 15px;
      background: var(--panel);
      box-shadow: 0 8px 24px #0008;
      animation: enter .25s ease both;
      overflow: hidden;
    }
    .request.processing { border-left-color: var(--blue); }
    .request.playing { border-left-color: var(--green); background: rgba(13, 34, 27, .95); }
    .avatar {
      position: relative;
      display: grid;
      place-items: center;
      width: 60px;
      height: 60px;
      border: 2px solid rgba(255, 255, 255, .78);
      border-radius: 50%;
      background: linear-gradient(145deg, #fb7299, #7655a5);
      box-shadow: 0 4px 14px #0008;
      overflow: hidden;
      font-size: 24px;
      font-weight: 900;
    }
    .avatar img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .song { min-width: 0; }
    .identity { display: flex; align-items: center; min-width: 0; height: 20px; margin-bottom: 1px; }
    .requester { flex: 0 1 auto; min-width: 0; color: var(--pink); font-size: 12px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .waiting { display: none; align-items: center; flex: 0 0 auto; min-width: 0; height: 20px; margin-left: 10px; padding-left: 10px; border-left: 1px solid rgba(255, 255, 255, .28); }
    .waiting.visible { display: flex; }
    .waiting-label { margin-right: 5px; color: var(--muted); font-size: 11px; font-weight: 800; white-space: nowrap; }
    .waiting-avatars { display: flex; align-items: center; }
    .waiting-avatar {
      position: relative;
      display: grid;
      place-items: center;
      width: 20px;
      height: 20px;
      margin-left: -4px;
      border: 1px solid rgba(255, 255, 255, .85);
      border-radius: 50%;
      background: linear-gradient(145deg, #fb7299, #7655a5);
      overflow: hidden;
      color: #fff;
      font-size: 9px;
      font-weight: 900;
      box-shadow: 0 1px 4px #0009;
    }
    .waiting-avatar:first-child { margin-left: 0; }
    .waiting-avatar img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .waiting-more { margin-left: 5px; color: var(--muted); font-size: 11px; font-weight: 800; white-space: nowrap; }
    .map { min-width: 0; color: var(--text); font-size: 19px; line-height: 23px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .difficulty { min-width: 0; color: var(--muted); font-size: 12px; line-height: 16px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    @keyframes enter { from { opacity: 0; transform: translateX(15px); } }
  </style>
</head>
<body>
  <main id="overlay"><section id="queue"></section></main>
  <script>
    const queueNode = document.getElementById('queue');
    let row = null;

    function reportHeight() {
      if (window.parent !== window) {
        requestAnimationFrame(() => {
          window.parent.postMessage(
            {type: 'bili-overlay-height', height: document.documentElement.scrollHeight},
            location.origin
          );
        });
      }
    }

    function makeRow(id) {
      const node = document.createElement('article');
      node.className = 'request';
      node.dataset.id = id;
      const avatar = document.createElement('div');
      avatar.className = 'avatar';
      const fallback = document.createElement('span');
      fallback.textContent = '♪';
      const image = document.createElement('img');
      image.alt = '';
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('error', () => { image.style.display = 'none'; });
      avatar.append(fallback, image);
      const song = document.createElement('div');
      song.className = 'song';
      const identity = document.createElement('div');
      identity.className = 'identity';
      const requester = document.createElement('div');
      requester.className = 'requester';
      const waiting = document.createElement('div');
      waiting.className = 'waiting';
      const waitingLabel = document.createElement('span');
      waitingLabel.className = 'waiting-label';
      const waitingAvatars = document.createElement('span');
      waitingAvatars.className = 'waiting-avatars';
      const waitingMore = document.createElement('span');
      waitingMore.className = 'waiting-more';
      waiting.append(waitingLabel, waitingAvatars, waitingMore);
      identity.append(requester, waiting);
      const map = document.createElement('div');
      map.className = 'map';
      const difficulty = document.createElement('div');
      difficulty.className = 'difficulty';
      song.append(identity, map, difficulty);
      node.append(avatar, song);
      node.parts = {
        image, requester, waiting, waitingLabel, waitingAvatars, waitingMore,
        map, difficulty
      };
      return node;
    }

    function renderWaiting(node, data) {
      const waiting = Array.isArray(data.overlay.waiting) ? data.overlay.waiting : [];
      const remaining = Number(data.overlay.remainingCount) || waiting.length;
      node.parts.waiting.classList.toggle('visible', remaining > 0);
      node.parts.waitingLabel.textContent = remaining > 0 ? `队列 ${remaining} 人` : '';
      node.parts.waitingAvatars.replaceChildren();
      for (const item of waiting.slice(0, 5)) {
        const avatar = document.createElement('span');
        avatar.className = 'waiting-avatar';
        avatar.title = item.requester || 'bilibili 观众';
        avatar.textContent = (item.requester || '?').trim().slice(0, 1);
        const avatarUrl = item.avatarUrl || '';
        if (avatarUrl) {
          const image = document.createElement('img');
          image.alt = '';
          image.referrerPolicy = 'no-referrer';
          image.addEventListener('error', () => image.remove());
          image.src = avatarUrl;
          avatar.append(image);
        }
        node.parts.waitingAvatars.append(avatar);
      }
      node.parts.waitingMore.textContent = remaining > 5 ? `+${remaining - 5}` : '';
    }

    function updateRow(node, item, data) {
      node.classList.toggle('processing', item.state === 'processing');
      node.classList.toggle('playing', Boolean(data.overlay.playing));
      node.parts.requester.textContent = item.requester || 'bilibili 观众';
      let title = item.overlayTitleLabel || '';
      let difficulty = item.overlayDifficulty || '';
      if (!title && item.currentMatch && data.tosu) {
        title = data.tosu.beatmapOverlayTitle || '';
        difficulty = difficulty || data.tosu.beatmapVersion || '';
      }
      node.parts.map.textContent = title || item.overlayMapLabel || item.mapLabel || item.reference || '正在解析谱面…';
      node.parts.difficulty.textContent = difficulty ? `[${difficulty}]` : '';
      renderWaiting(node, data);
      const avatarUrl = item.avatarUrl || '';
      if (node.parts.image.dataset.url !== avatarUrl) {
        node.parts.image.dataset.url = avatarUrl;
        node.parts.image.style.display = avatarUrl ? 'block' : 'none';
        if (avatarUrl) node.parts.image.src = avatarUrl;
        else node.parts.image.removeAttribute('src');
      }
    }

    function render(data) {
      const item = data.overlay && data.overlay.current;
      if (!item) {
        queueNode.replaceChildren();
        row = null;
        reportHeight();
        return;
      }
      const id = String(item.id);
      if (!row || row.dataset.id !== id) {
        row = makeRow(id);
        queueNode.replaceChildren(row);
      }
      updateRow(row, item, data);
      reportHeight();
    }

    async function refresh() {
      try {
        const response = await fetch('/api/status', {cache: 'no-store'});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        render(await response.json());
      } catch (_) {
        queueNode.replaceChildren();
        row = null;
        reportHeight();
      }
    }
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class DashboardServer:
    def __init__(
        self,
        port: int,
        status_provider: Callable[[], dict],
    ) -> None:
        self.port = port
        self.status_provider = status_provider
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application(client_max_size=128 * 1024)
        app.router.add_get("/", self._index)
        app.router.add_get("/overlay", self._overlay)
        app.router.add_get("/api/status", self._status)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await site.start()
        logger.info("Web 队列页面：http://127.0.0.1:%d/", self.port)

    async def close(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _index(self, _request: web.Request) -> web.Response:
        return web.Response(
            text=_DASHBOARD_HTML,
            content_type="text/html",
            charset="utf-8",
            headers={"Cache-Control": "no-store"},
        )

    async def _status(self, _request: web.Request) -> web.Response:
        return web.json_response(
            self.status_provider(),
            headers={"Cache-Control": "no-store"},
        )

    async def _overlay(self, _request: web.Request) -> web.Response:
        return web.Response(
            text=_OVERLAY_HTML,
            content_type="text/html",
            charset="utf-8",
            headers={"Cache-Control": "no-store"},
        )
