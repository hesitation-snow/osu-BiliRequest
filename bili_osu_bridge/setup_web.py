from __future__ import annotations

import asyncio
import logging
import webbrowser
from pathlib import Path
from typing import Any

from aiohttp import web

from .bili_login import generate_qr_ticket, poll_qr_ticket
from .config import Config


logger = logging.getLogger(__name__)


def _default_config() -> Config:
    return Config(
        bili_room_id=0,
        bili_sessdata="",
        osu_irc_username="",
        osu_irc_password="",
        osu_target_username="",
        osu_api_enabled=True,
    )


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        values = value
    else:
        values = str(value or "").replace(",", "\n").splitlines()
    return tuple(str(item).strip() for item in values if str(item).strip())


def _number(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    return float(default if value in {None, ""} else value)


def build_config_from_payload(
    data: dict[str, Any],
    current: Config | None = None,
) -> Config:
    base = current or _default_config()
    sessdata = str(data.get("sessdata") or "").strip()
    if bool(data.get("clearSessdata")):
        sessdata = ""
    elif not sessdata:
        sessdata = base.bili_sessdata

    irc_password = str(data.get("ircPassword") or "").strip()
    if not irc_password:
        irc_password = base.osu_irc_password
    api_secret = str(data.get("apiClientSecret") or "").strip()
    if not api_secret:
        api_secret = base.osu_api_client_secret

    config = Config(
        bili_room_id=int(data.get("roomId") or 0),
        bili_sessdata=sessdata,
        osu_irc_username=str(data.get("ircUsername") or "").strip(),
        osu_irc_password=irc_password,
        osu_target_username=str(data.get("targetUsername") or "").strip(),
        osu_api_enabled=bool(data.get("apiEnabled")),
        osu_api_client_id=int(data.get("apiClientId") or 0),
        osu_api_client_secret=api_secret,
        request_keywords=_strings(data.get("requestKeywords") or "点歌"),
        tosu_enabled=bool(data.get("tosuEnabled")),
        tosu_url=str(
            data.get("tosuUrl") or "http://127.0.0.1:24050/json/v2"
        ).strip(),
        tosu_poll_interval_seconds=_number(data, "tosuPollSeconds", 1),
        use_unicode_irc=bool(data.get("useUnicodeIrc")),
        use_unicode_web=bool(data.get("useUnicodeWeb")),
        use_unicode_overlay=bool(data.get("useUnicodeOverlay")),
        web_port=int(data.get("webPort") or 24051),
        overlay_hold_seconds=_number(data, "overlayHoldSeconds", 300),
        overlay_matched_hold_seconds=_number(
            data, "overlayMatchedHoldSeconds", 120
        ),
        overlay_played_hold_seconds=_number(
            data, "overlayPlayedHoldSeconds", 60
        ),
        user_cooldown_seconds=_number(data, "userCooldownSeconds", 30),
        map_dedupe_seconds=_number(data, "mapDedupeSeconds", 600),
        queue_max_size=int(data.get("queueMaxSize") or 50),
        irc_send_interval_seconds=_number(data, "ircSendIntervalSeconds", 1),
        send_startup_message=bool(data.get("sendStartupMessage")),
        proxy_url=str(data.get("proxy") or "").strip(),
        blacklisted_user_ids=_strings(data.get("blacklistedUserIds")),
        blacklisted_usernames=_strings(data.get("blacklistedUsernames")),
        log_level=str(data.get("logLevel") or "INFO").strip().upper(),
    )
    config.validate()
    return config


_SETUP_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>osu-BiliRequest 设置</title>
  <style>
    :root { color-scheme: dark; --bg:#0b0e16; --panel:#171b27; --line:#2b3244; --text:#f5f7fc; --muted:#9da7ba; --pink:#fb7299; --blue:#65c7ff; --green:#6de3a1; --red:#ff7890; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font:14px/1.55 "Segoe UI","Microsoft YaHei",sans-serif; background:radial-gradient(circle at 10% 0,#47213f 0,transparent 30rem),radial-gradient(circle at 100% 15%,#123c58 0,transparent 34rem),var(--bg); }
    main { width:min(980px,calc(100% - 28px)); margin:auto; padding:34px 0 70px; }
    header { margin-bottom:22px; }
    h1 { margin:0; font-size:clamp(30px,6vw,52px); letter-spacing:-2px; } h1 span { color:var(--pink); }
    .lead,.hint { color:var(--muted); } .lead { font-size:16px; }
    .warning { margin:18px 0; padding:13px 15px; border:1px solid #5d3b46; border-radius:12px; background:#291923d9; color:#ffc8d7; }
    .notice { grid-column:1/-1; padding:11px 13px; border:1px solid #66592f; border-radius:10px; background:#2a2517; color:#ffe49a; }
    form { display:grid; gap:15px; }
    section { padding:20px; border:1px solid var(--line); border-radius:18px; background:#171b27e9; box-shadow:0 15px 50px #0004; }
    .section-head { display:flex; justify-content:space-between; gap:12px; align-items:start; margin-bottom:14px; }
    h2 { margin:0; font-size:19px; } .tag { color:var(--pink); font-size:12px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px; }
    .full { grid-column:1/-1; }
    label { display:grid; gap:5px; color:#dce1ed; font-weight:650; }
    input,textarea,select { width:100%; border:1px solid #3a4359; border-radius:10px; padding:10px 11px; background:#10141e; color:var(--text); font:inherit; outline:none; }
    input:focus,textarea:focus,select:focus { border-color:var(--pink); box-shadow:0 0 0 3px #fb72991d; }
    textarea { min-height:76px; resize:vertical; }
    .switch { display:flex; align-items:center; gap:9px; min-height:42px; font-weight:700; }
    .switch input { width:18px; height:18px; accent-color:var(--pink); }
    a { color:var(--blue); }
    button { border:1px solid #4a5570; border-radius:10px; padding:10px 15px; background:#252c3e; color:var(--text); font:inherit; font-weight:800; cursor:pointer; }
    button:hover { border-color:var(--pink); color:#ffc2d5; }
    button.primary { border-color:#fb7299; background:linear-gradient(135deg,#fb7299,#d95787); color:white; font-size:16px; }
    button:disabled { opacity:.55; cursor:wait; }
    .qr-row { display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
    #qr-image { display:none; width:170px; height:170px; border:8px solid white; border-radius:12px; image-rendering:auto; }
    #qr-status.success { color:var(--green); } #qr-status.error,#message.error { color:var(--red); }
    .api-fields.disabled,.tosu-fields.disabled { opacity:.45; pointer-events:none; }
    .actions { position:sticky; bottom:10px; display:flex; justify-content:space-between; align-items:center; gap:15px; padding:14px 16px; border:1px solid #3b4358; border-radius:15px; background:#111621f2; box-shadow:0 10px 36px #000a; backdrop-filter:blur(14px); }
    #message { min-height:22px; font-weight:750; }
    @media(max-width:700px){ .grid{grid-template-columns:1fr}.full{grid-column:auto}.actions{align-items:stretch;flex-direction:column}.actions button{width:100%} }
  </style>
</head>
<body><main>
  <header><h1><span>osu</span>-BiliRequest 设置</h1><div class="lead">本地 Web 配置向导 · 所有内容只保存到程序旁的 config.json</div></header>
  <div class="warning">请勿公开分享 config.json。它包含登录用户名、IRC 密码、Cookie 和 Client Secret。<br>Do not share config.json publicly; it contains login credentials and secrets.</div>
  <form id="form">
    <section><div class="section-head"><div><h2>bilibili 直播间</h2><div class="hint">登录后可读取完整弹幕用户名；匿名连接可能显示 M***。</div></div><span class="tag">01</span></div>
      <div class="grid">
        <label class="full">直播间号<input id="roomId" type="number" min="1" required></label>
        <label class="full">手动填写 SESSDATA（留空会保留已有登录）<input id="sessdata" type="password" autocomplete="off" placeholder="可选；推荐使用下方二维码登录"></label>
        <label class="switch full"><input id="clearSessdata" type="checkbox">清除已有登录并使用匿名模式</label>
        <div class="full qr-row"><button id="qr-button" type="button">使用 bilibili 手机客户端扫码登录</button><img id="qr-image" alt="bilibili 登录二维码"><span id="qr-status" class="hint"></span></div>
      </div>
    </section>

    <section><div class="section-head"><div><h2>网络代理</h2><div class="hint">留空表示直连；用于 bilibili、osu! API/网页、弹幕 WebSocket 和 Bancho IRC，不影响 tosu 本机连接。</div></div><span class="tag">02</span></div>
      <div class="grid"><label class="full">HTTP 代理<input id="proxy" placeholder="例如 http://127.0.0.1:7890"></label></div>
    </section>

    <section><div class="section-head"><div><h2>osu! Bancho IRC</h2><div class="hint">点歌转发的必需功能。使用 IRC 专用密码，不是游戏登录密码。<a href="https://osu.ppy.sh/home/account/edit#Legacy_api" target="_blank" rel="noreferrer">获取 IRC 密码</a></div></div><span class="tag">03</span></div>
      <div class="grid">
        <div class="notice"><strong>osu!lazer 注意：</strong>lazer 无法在游戏内收到自己的 IRC 账号发给自己的消息。如果使用 lazer，请将“IRC 用户名”和“游戏内接收者用户名”设置为两个不同的 osu! 账号；或者改用 osu!stable 接收。</div>
        <label>IRC 用户名<input id="ircUsername" required></label>
        <label>游戏内接收者用户名<input id="targetUsername" required></label>
        <label>IRC 专用密码（留空会保留已有密码）<input id="ircPassword" type="password" autocomplete="new-password"></label>
        <label>最小发送间隔（秒）<input id="ircSendIntervalSeconds" type="number" min="0.5" step="0.1"></label>
        <label class="switch full"><input id="sendStartupMessage" type="checkbox">启动后向接收者发送连接成功消息</label>
      </div>
    </section>

    <section><div class="section-head"><div><h2>osu! API</h2><div class="hint">用于获取谱面资料、难度信息及 Mods 后的真实星数；失败时自动回退网页解析和 base 星数。<a href="https://osu.ppy.sh/home/account/edit#oauth" target="_blank" rel="noreferrer">创建 OAuth 应用</a></div></div><span class="tag">04</span></div>
      <label class="switch"><input id="apiEnabled" type="checkbox">启用 osu! API</label>
      <div id="api-fields" class="grid api-fields">
        <label>OAuth Client ID<input id="apiClientId" type="number" min="0"></label>
        <label>Client Secret（留空会保留已有值）<input id="apiClientSecret" type="password" autocomplete="new-password"></label>
      </div>
    </section>

    <section><div class="section-head"><div><h2>tosu 状态同步</h2><div class="hint">开启后可判断点歌是否为当前谱面、同步 play/selectPlay 状态，并自动推进 Overlay 队列。关闭不影响弹幕监听和 IRC 点歌。</div></div><span class="tag">05</span></div>
      <label class="switch"><input id="tosuEnabled" type="checkbox">启用 tosu 状态同步</label>
      <div id="tosu-fields" class="grid tosu-fields">
        <label class="full">tosu v2 JSON 地址<input id="tosuUrl"></label>
        <label>轮询间隔（秒）<input id="tosuPollSeconds" type="number" min="0.25" step="0.25"></label>
      </div>
    </section>

    <section><div class="section-head"><div><h2>显示与 Overlay</h2><div class="hint">三个位置可以分别选择歌名格式；Unicode 字段为空的老谱面会自动回退普通 Artist/Title。</div></div><span class="tag">06</span></div>
      <div class="grid">
        <label class="switch full"><input id="useUnicodeIrc" type="checkbox">IRC 推送优先使用 Unicode Artist/Title（默认关闭）</label>
        <label class="switch full"><input id="useUnicodeWeb" type="checkbox">Web 队列优先使用 Unicode Artist/Title（默认开启）</label>
        <label class="switch full"><input id="useUnicodeOverlay" type="checkbox">OBS Overlay 优先使用 Unicode Artist/Title（默认开启）</label>
        <label>Web 端口<input id="webPort" type="number" min="1" max="65535"></label>
        <label>未游玩保留时间（秒）<input id="overlayHoldSeconds" type="number" min="0" max="3600"></label>
        <label>同谱已选中但未开始（秒）<input id="overlayMatchedHoldSeconds" type="number" min="0" max="3600"></label>
        <label>游玩结束仍未切谱面（秒）<input id="overlayPlayedHoldSeconds" type="number" min="0" max="3600"></label>
      </div>
    </section>

    <section><div class="section-head"><div><h2>点歌规则</h2><div class="hint">关键词、冷却、去重、黑名单都可以在这里调整。</div></div><span class="tag">07</span></div>
      <div class="grid">
        <label class="full">弹幕关键词（每行一个）<textarea id="requestKeywords"></textarea></label>
        <label>单用户冷却（秒）<input id="userCooldownSeconds" type="number" min="0"></label>
        <label>同谱去重（秒）<input id="mapDedupeSeconds" type="number" min="0"></label>
        <label>内部最大队列<input id="queueMaxSize" type="number" min="1"></label>
        <label>日志等级<select id="logLevel"><option>INFO</option><option>DEBUG</option><option>WARNING</option><option>ERROR</option></select></label>
        <label>黑名单 UID（每行一个）<textarea id="blacklistedUserIds"></textarea></label>
        <label>黑名单用户名（每行一个）<textarea id="blacklistedUsernames"></textarea></label>
      </div>
    </section>

    <div class="actions"><div id="message" class="hint">保存后会写入 config.json；程序运行中修改配置时，请重启应用以完全生效。</div><button id="save" class="primary" type="submit">保存配置</button></div>
  </form>
</main>
<script>
  const byId = id => document.getElementById(id);
  let qrSessdata = '';
  let qrTimer = null;
  const checkboxIds = ['sendStartupMessage','apiEnabled','tosuEnabled','useUnicodeIrc','useUnicodeWeb','useUnicodeOverlay'];

  function toggleGroups() {
    byId('api-fields').classList.toggle('disabled', !byId('apiEnabled').checked);
    byId('tosu-fields').classList.toggle('disabled', !byId('tosuEnabled').checked);
  }
  byId('apiEnabled').addEventListener('change', toggleGroups);
  byId('tosuEnabled').addEventListener('change', toggleGroups);

  async function loadConfig() {
    const response = await fetch('/settings/api/config', {cache:'no-store'});
    const data = await response.json();
    for (const [key,value] of Object.entries(data.values)) {
      const node = byId(key);
      if (!node) continue;
      if (node.type === 'checkbox') node.checked = Boolean(value);
      else node.value = value ?? '';
    }
    if (data.hasSessdata) byId('sessdata').placeholder = '已保存登录；留空保持不变';
    if (data.hasIrcPassword) byId('ircPassword').placeholder = '已保存密码；留空保持不变';
    if (data.hasApiSecret) byId('apiClientSecret').placeholder = '已保存 Secret；留空保持不变';
    toggleGroups();
  }

  async function pollQr(key) {
    const params = new URLSearchParams({key, proxy:byId('proxy').value.trim()});
    const response = await fetch(`/settings/api/qr/poll?${params}`, {cache:'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    byId('qr-status').textContent = data.message;
    if (data.status === 'success') {
      clearInterval(qrTimer); qrTimer = null;
      qrSessdata = data.sessdata;
      byId('clearSessdata').checked = false;
      byId('qr-status').className = 'success';
      byId('qr-status').textContent = `登录成功${data.username ? `：${data.username}` : ''}`;
      return true;
    } else if (['expired','error'].includes(data.status)) {
      clearInterval(qrTimer); qrTimer = null;
      byId('qr-status').className = 'error';
      return true;
    }
    return false;
  }

  byId('qr-button').addEventListener('click', async () => {
    const button = byId('qr-button'); button.disabled = true;
    byId('qr-status').className = 'hint'; byId('qr-status').textContent = '正在生成二维码…';
    try {
      const response = await fetch('/settings/api/qr/start', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({proxy:byId('proxy').value.trim()})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      byId('qr-image').src = data.image; byId('qr-image').style.display = 'block';
      byId('qr-status').textContent = '请使用 bilibili 手机客户端扫码并确认';
      if (qrTimer) clearInterval(qrTimer);
      const finished = await pollQr(data.key);
      if (!finished) qrTimer = setInterval(() => pollQr(data.key).catch(showError), 2000);
    } catch (error) { showError(error); }
    finally { button.disabled = false; }
  });

  function showError(error) {
    byId('message').className = 'error';
    byId('message').textContent = error.message || String(error);
  }

  byId('form').addEventListener('submit', async event => {
    event.preventDefault();
    const save = byId('save'); save.disabled = true;
    const payload = {
      roomId:byId('roomId').value, proxy:byId('proxy').value,
      sessdata:byId('sessdata').value || qrSessdata, clearSessdata:byId('clearSessdata').checked,
      ircUsername:byId('ircUsername').value, targetUsername:byId('targetUsername').value,
      ircPassword:byId('ircPassword').value, ircSendIntervalSeconds:byId('ircSendIntervalSeconds').value,
      sendStartupMessage:byId('sendStartupMessage').checked,
      apiEnabled:byId('apiEnabled').checked, apiClientId:byId('apiClientId').value,
      apiClientSecret:byId('apiClientSecret').value,
      tosuEnabled:byId('tosuEnabled').checked, tosuUrl:byId('tosuUrl').value,
      tosuPollSeconds:byId('tosuPollSeconds').value,
      useUnicodeIrc:byId('useUnicodeIrc').checked,
      useUnicodeWeb:byId('useUnicodeWeb').checked,
      useUnicodeOverlay:byId('useUnicodeOverlay').checked,
      webPort:byId('webPort').value,
      overlayHoldSeconds:byId('overlayHoldSeconds').value,
      overlayMatchedHoldSeconds:byId('overlayMatchedHoldSeconds').value,
      overlayPlayedHoldSeconds:byId('overlayPlayedHoldSeconds').value,
      requestKeywords:byId('requestKeywords').value,
      userCooldownSeconds:byId('userCooldownSeconds').value,
      mapDedupeSeconds:byId('mapDedupeSeconds').value, queueMaxSize:byId('queueMaxSize').value,
      blacklistedUserIds:byId('blacklistedUserIds').value,
      blacklistedUsernames:byId('blacklistedUsernames').value, logLevel:byId('logLevel').value
    };
    try {
      const response = await fetch('/settings/api/save', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      if (qrTimer) clearInterval(qrTimer);
      byId('message').className = 'success';
      byId('message').textContent = '配置已保存。首次运行会自动继续；若程序已在运行，请重启应用以完全生效。';
      save.textContent = '保存成功';
    } catch (error) { showError(error); save.disabled = false; }
  });
  loadConfig().catch(showError);
</script></body></html>"""


class SetupWebServer:
    def __init__(self, config_path: Path, listen_port: int | None = None) -> None:
        self.config_path = config_path
        self.current: Config | None = None
        if config_path.exists():
            try:
                self.current = Config.load(config_path, validate=False)
            except Exception as exc:
                logger.warning("现有配置无法读取，将使用默认值：%s", exc)
        self.listen_port = (
            listen_port
            if listen_port is not None
            else (self.current.web_port if self.current is not None else 24051)
        )
        self.saved = asyncio.Event()
        self.saved_config: Config | None = None
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self.port = 0

    def _public_config(self) -> dict[str, Any]:
        config = self.current or _default_config()
        return {
            "values": {
                "roomId": config.bili_room_id or "",
                "proxy": config.proxy_url,
                "ircUsername": config.osu_irc_username,
                "targetUsername": config.osu_target_username,
                "ircSendIntervalSeconds": config.irc_send_interval_seconds,
                "sendStartupMessage": config.send_startup_message,
                "apiEnabled": config.osu_api_enabled,
                "apiClientId": config.osu_api_client_id or "",
                "tosuEnabled": config.tosu_enabled,
                "tosuUrl": config.tosu_url,
                "tosuPollSeconds": config.tosu_poll_interval_seconds,
                "useUnicodeIrc": config.use_unicode_irc,
                "useUnicodeWeb": config.use_unicode_web,
                "useUnicodeOverlay": config.use_unicode_overlay,
                "webPort": config.web_port,
                "overlayHoldSeconds": config.overlay_hold_seconds,
                "overlayMatchedHoldSeconds": config.overlay_matched_hold_seconds,
                "overlayPlayedHoldSeconds": config.overlay_played_hold_seconds,
                "requestKeywords": "\n".join(config.request_keywords),
                "userCooldownSeconds": config.user_cooldown_seconds,
                "mapDedupeSeconds": config.map_dedupe_seconds,
                "queueMaxSize": config.queue_max_size,
                "blacklistedUserIds": "\n".join(config.blacklisted_user_ids),
                "blacklistedUsernames": "\n".join(config.blacklisted_usernames),
                "logLevel": config.log_level,
            },
            "hasSessdata": bool(config.bili_sessdata),
            "hasIrcPassword": bool(config.osu_irc_password),
            "hasApiSecret": bool(config.osu_api_client_secret),
        }

    def add_routes(self, app: web.Application, *, include_root: bool = False) -> None:
        if include_root:
            app.router.add_get("/", self._redirect_to_settings)
        app.router.add_get("/settings", self._index)
        app.router.add_get("/settings/", self._index)
        app.router.add_get("/settings/api/config", self._get_config)
        app.router.add_post("/settings/api/save", self._save)
        app.router.add_post("/settings/api/qr/start", self._qr_start)
        app.router.add_get("/settings/api/qr/poll", self._qr_poll)

    async def start(self) -> None:
        app = web.Application(client_max_size=128 * 1024)
        self.add_routes(app, include_root=True)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", self.listen_port)
        await self.site.start()
        sockets = self.site._server.sockets if self.site._server else []
        if not sockets:
            raise RuntimeError("无法取得 Web 设置页端口")
        self.port = int(sockets[0].getsockname()[1])

    async def close(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None

    async def _redirect_to_settings(self, _request: web.Request) -> web.Response:
        raise web.HTTPFound("/settings")

    async def _index(self, _request: web.Request) -> web.Response:
        return web.Response(
            text=_SETUP_HTML,
            content_type="text/html",
            charset="utf-8",
            headers={"Cache-Control": "no-store"},
        )

    async def _get_config(self, _request: web.Request) -> web.Response:
        return web.json_response(self._public_config(), headers={"Cache-Control": "no-store"})

    async def _save(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("提交内容必须是 JSON 对象")
            config = build_config_from_payload(payload, self.current)
            config.save(self.config_path)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)
        self.current = config
        self.saved_config = config
        self.saved.set()
        return web.json_response({"ok": True})

    async def _qr_start(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
            proxy = str((payload or {}).get("proxy") or "").strip()
            ticket = await generate_qr_ticket(proxy)
            return web.json_response({"key": ticket.key, "image": ticket.image_data_url})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

    async def _qr_poll(self, request: web.Request) -> web.Response:
        try:
            result = await poll_qr_ticket(
                request.query.get("key", ""),
                request.query.get("proxy", "").strip(),
            )
            return web.json_response(
                {
                    "status": result.status,
                    "message": result.message,
                    "sessdata": result.sessdata,
                    "username": result.username,
                }
            )
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)


async def run_setup_web(config_path: Path) -> Config:
    server = SetupWebServer(config_path)
    await server.start()
    url = f"http://127.0.0.1:{server.port}/settings"
    print(f"Web 设置向导已启动：{url}", flush=True)
    print("请在浏览器中填写并保存配置；不要关闭此窗口。", flush=True)
    try:
        await asyncio.to_thread(webbrowser.open, url)
        await server.saved.wait()
        await asyncio.sleep(0.5)
    finally:
        await server.close()
    if server.saved_config is None:
        raise RuntimeError("配置尚未保存")
    return server.saved_config
