(() => {
  "use strict";

  const query = new URLSearchParams(location.search);
  const bridgeHost = query.get("bridgeHost") || "127.0.0.1";
  const bridgePort = query.get("bridgePort") || "24051";
  const bridgeWs = query.get("bridgeWs") || `ws://${bridgeHost}:${bridgePort}/api/v1/ws`;
  const localWsProtocol = location.protocol === "https:" ? "wss:" : "ws:";
  const tosuHost = location.port === "24050" ? location.host : "127.0.0.1:24050";
  const tosuWs = query.get("tosuWs") || `${localWsProtocol}//${tosuHost}/websocket/v2`;
  const debugEnabled = query.get("debug") === "1";

  const card = document.getElementById("request-card");
  const avatar = document.getElementById("avatar");
  const avatarFallback = document.getElementById("avatar-fallback");
  const requester = document.getElementById("requester");
  const title = document.getElementById("title");
  const meta = document.getElementById("meta");
  const waiting = document.getElementById("waiting");
  const waitingAvatars = document.getElementById("waiting-avatars");
  const waitingCount = document.getElementById("waiting-count");
  const debug = document.getElementById("debug");

  let bridgeData = null;
  let tosuData = null;
  let visibleId = null;
  let transitioning = false;
  let pendingRender = false;
  const connections = { bridge: false, tosu: false };

  function reconnectingSocket(name, url, onPayload) {
    let stopped = false;
    let retry = 1000;

    const open = () => {
      if (stopped) return;
      const socket = new WebSocket(url);

      socket.addEventListener("open", () => {
        connections[name] = true;
        retry = 1000;
        renderDebug();
      });
      socket.addEventListener("message", event => {
        try {
          onPayload(JSON.parse(event.data));
        } catch (error) {
          if (debugEnabled) console.warn(`${name} payload error`, error);
        }
      });
      socket.addEventListener("close", () => {
        connections[name] = false;
        renderDebug();
        if (!stopped) {
          setTimeout(open, retry);
          retry = Math.min(Math.round(retry * 1.6), 10000);
        }
      });
      socket.addEventListener("error", () => socket.close());
    };

    open();
    return () => { stopped = true; };
  }

  function unwrapTosu(payload) {
    if (payload && payload.beatmap) return payload;
    if (payload && payload.data && payload.data.beatmap) return payload.data;
    return payload || {};
  }

  function tosuState() {
    const state = tosuData && tosuData.state;
    return String(state && typeof state === "object" ? state.name || "" : state || "");
  }

  function tosuBeatmapId() {
    const beatmap = tosuData && tosuData.beatmap;
    const value = beatmap && (beatmap.id || beatmap.mapID || beatmap.mapId);
    const number = Number(value || 0);
    return Number.isFinite(number) ? number : 0;
  }

  function isPlaying(item) {
    if (bridgeData && bridgeData.overlay && bridgeData.overlay.playing) return true;
    const state = tosuState().toLowerCase();
    return state === "play" && Number(item.resolvedBeatmapId || 0) === tosuBeatmapId();
  }

  function setAvatar(container, fallbackNode, item) {
    container.querySelectorAll("img").forEach(image => image.remove());
    const name = String(item.requester || "观众").trim();
    fallbackNode.textContent = name.slice(0, 1) || "?";
    const url = item.overlayAvatarUrl || item.avatarUrl || "";
    if (!url) return;
    const image = document.createElement("img");
    image.alt = "";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => image.remove());
    image.src = url;
    container.append(image);
  }

  function renderWaiting(overlay) {
    const items = Array.isArray(overlay.waiting) ? overlay.waiting : [];
    const remaining = Number(overlay.remainingCount || items.length || 0);
    waiting.hidden = remaining <= 0;
    waitingAvatars.replaceChildren();

    for (const item of items.slice(0, 5).reverse()) {
      const node = document.createElement("span");
      node.className = "waiting-avatar";
      node.title = item.requester || "观众";
      const fallback = document.createElement("span");
      fallback.textContent = String(item.requester || "?").trim().slice(0, 1) || "?";
      node.append(fallback);
      const url = item.overlayAvatarUrl || item.avatarUrl || "";
      if (url) {
        const image = document.createElement("img");
        image.alt = "";
        image.referrerPolicy = "no-referrer";
        image.addEventListener("error", () => image.remove());
        image.src = url;
        node.append(image);
      }
      waitingAvatars.append(node);
    }
    waitingCount.textContent = `队列 ${remaining} 人`;
  }

  function updateCard(item, overlay) {
    requester.textContent = item.requester || "观众";
    title.textContent = item.overlayTitleLabel || item.overlayMapLabel || item.mapLabel || item.reference || "正在解析谱面…";
    meta.textContent = [
      item.overlayDifficulty ? `[${item.overlayDifficulty}]` : "",
      item.durationLabel || "",
      item.starsLabel || ""
    ].filter(Boolean).join(" · ");
    setAvatar(avatar, avatarFallback, item);
    renderWaiting(overlay);
    card.classList.toggle("playing", isPlaying(item));
  }

  function show(item, overlay) {
    visibleId = String(item.id);
    card.hidden = false;
    card.classList.remove("leaving");
    card.classList.add("entering");
    updateCard(item, overlay);
    requestAnimationFrame(() => requestAnimationFrame(() => card.classList.remove("entering")));
  }

  function hideThenRender() {
    transitioning = true;
    card.classList.remove("entering");
    card.classList.add("leaving");
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      card.removeEventListener("transitionend", onEnd);
      card.hidden = true;
      card.classList.remove("leaving");
      visibleId = null;
      transitioning = false;
      const shouldRender = pendingRender;
      pendingRender = false;
      if (shouldRender) render();
    };
    const onEnd = event => {
      if (event.propertyName === "opacity") finish();
    };
    card.addEventListener("transitionend", onEnd);
    setTimeout(finish, 800);
  }

  function render() {
    renderDebug();
    const overlay = bridgeData && bridgeData.overlay || {};
    const item = overlay.current || null;
    if (transitioning) {
      pendingRender = true;
      return;
    }
    if (!item) {
      if (!card.hidden) hideThenRender();
      return;
    }
    if (visibleId === String(item.id) && !card.hidden) {
      updateCard(item, overlay);
      return;
    }
    if (!card.hidden) {
      pendingRender = true;
      hideThenRender();
      return;
    }
    show(item, overlay);
  }

  function renderDebug() {
    if (!debugEnabled) return;
    debug.hidden = false;
    debug.textContent = `osu-BiliRequest WS: ${connections.bridge ? "OK" : "reconnecting"} · tosu WS: ${connections.tosu ? "OK" : "reconnecting"} · ${tosuState() || "unknown"} · b/${tosuBeatmapId() || 0}`;
  }

  reconnectingSocket("bridge", bridgeWs, message => {
    if (message && message.type === "status" && message.data) {
      bridgeData = message.data;
      render();
    }
  });

  reconnectingSocket("tosu", tosuWs, payload => {
    tosuData = unwrapTosu(payload);
    render();
  });
})();
