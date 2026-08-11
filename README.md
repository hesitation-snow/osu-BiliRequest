# osu-BiliRequest

`osu-BiliRequest` 是一个本地运行的 bilibili 直播点歌桥接器。它监听直播间普通弹幕，识别 osu! Beatmap/Beatmapset 请求，查询谱面信息，再通过 Bancho IRC 私聊发送到游戏内，同时提供本地队列页面、tosu 状态同步和 OBS Overlay。

## 功能汇总

### 弹幕与点歌

- 监听指定 bilibili 直播间的普通文字弹幕，支持二维码登录、手动 SESSDATA 和匿名监听。
- 识别纯数字 Beatmap ID、`b/` 难度 ID、`s/` 谱面集 ID；`s/` 自动选择谱面集中星数最高的难度。
- 支持自定义点歌关键词，以及 `HD`、`HR`、`DT`、`NC`、`HT` 等 Mods 和冲突组合校验。
- 提供用户冷却、同谱去重、最大队列、UID/用户名黑名单。

### 谱面查询与 IRC

- 通过 osu! API 或官方谱面页获取 Ranked Status、Artist、Title、难度名、BPM、星数和长度。
- 配置 osu! API 后可查询 Mods 后的真实星数；API 不可用时自动回退网页解析。
- 通过 Bancho IRC 私聊发送点歌，包含 osu! 谱面链接，以及 Sayobot 的完整包与无视频包下载链接。

### Web 队列、tosu 与 OBS

- 本地 Web 页面显示队列状态、点歌者头像和用户名、谱面资料及当前谱面匹配结果。
- 可连接 tosu，同步当前 Beatmap 与 `play`/`selectPlay` 状态，自动识别选谱、开始和结束游玩。
- OBS 透明 Overlay 显示当前点歌、难度、点歌者信息、队列人数和后续用户头像；无人点歌时保持透明。

## 快速开始

1. 从 [Releases](https://github.com/hesitation-snow/osu-BiliRequest/releases) 下载 `osu-BiliRequest.exe`，放入一个单独文件夹。程序会在同一文件夹生成配置和日志，请不要在压缩包或系统目录中运行。
2. 双击 `osu-BiliRequest.exe`。首次运行会自动在浏览器打开 Web 设置向导。
3. 填写 bilibili 直播间号、osu! Bancho IRC 用户名、IRC 专用密码和游戏内接收者；根据需要配置 bilibili 登录、osu! API、HTTP 代理与 tosu。
4. 点击“保存配置”。程序会生成 `config.json`、继续启动服务，并在默认浏览器打开 Web 队列页面 `http://127.0.0.1:24051/`。
5. 保持程序窗口运行。观众发送符合格式的弹幕后，点歌会进入 Web 队列并通过 Bancho IRC 推送；需要 OBS 显示时，再添加页面提供的 Overlay 地址。

以后直接双击同一个 EXE 即可启动。需要修改设置时，关闭程序后手动编辑 `config.json`；使用本地分发包或源码时，也可以双击 `configure.bat` 重新打开设置向导，保存后再启动程序。

设置向导和队列页面仅监听 `127.0.0.1` 本机地址，不会直接暴露到局域网或公网。密码、Cookie 和 Client Secret 不会在页面中回显；敏感输入框留空会保留已经保存的值。请勿公开分享 `config.json`。

## Web 设置向导

设置页包含：

- bilibili 直播间号、二维码登录、手动 SESSDATA、匿名模式。
- 独立的网络代理设置。
- osu! IRC 用户名、专用密码、游戏内接收者、发送间隔、启动消息。
- osu! API 开关、Client ID 和 Client Secret。
- tosu 开关、v2 JSON 地址和轮询间隔。
- IRC、Web、Overlay 三个独立的 Unicode Artist/Title 开关，以及 Web 端口和 Overlay 保留时间。
- 点歌关键词、用户冷却、谱面去重、最大队列、黑名单和日志等级。

二维码登录需要使用 bilibili 手机客户端扫码并在手机上确认。成功后 SESSDATA 会随保存操作写入 `config.json`，页面不会显示 Cookie 内容。

osu! IRC 专用密码：[osu! Legacy API 设置](https://osu.ppy.sh/home/account/edit#Legacy_api)

osu! OAuth 应用：[osu! OAuth 设置](https://osu.ppy.sh/home/account/edit#oauth)

## 支持的弹幕格式

```text
123456
点歌123456
点歌 123456
点歌：123456
b/5600294
点歌 b/5600294
s/2533001
点歌 s/2533001
b/5600294 +HDDT
点歌 s/2533001 +HD +DT
```

- 纯数字和 `b/` 表示指定难度的 Beatmap ID。
- `s/` 表示 Beatmapset ID，程序自动选取最高星难度。
- Mods 支持 `+HDDT`、`+HD +DT`、`HD DT` 等形式。
- 重复 Mods 会合并；`DT+HT`、`EZ+HR` 等冲突组合会拒绝。
- 完整网址或夹杂其它聊天内容的消息不会被当作点歌。
- 非普通文字弹幕不会处理。

## osu! IRC 推送格式

成功读取谱面信息时：

```text
[Miarru] -> [Ranked] [Zektbach - The Sealer 〜ア・ミリアとミリアの民〜 [921206025887's Extra]] (205 BPM, 6.11*, 2:03) [Sayobot Full] [Sayobot NoVideo]
```

配置 osu! API 后，程序优先通过 API 取得谱面资料与难度，并读取真实 Mod 星数；API 失败时自动回退 osu! 网页解析和 `base 5.79*`。如果两种谱面来源都暂时不可用，仍会发送包含 Beatmap ID 的基础链接，不会丢弃点歌。DT/NC/HT 会调整显示的 BPM 和长度；有 Mods 时显示在参数之后。`Sayobot Full` 下载完整包，`Sayobot NoVideo` 下载不含视频的版本。

启动时默认向接收者发送：

```text
[osu-BiliRequest] 连接成功，正在监听直播间 268086。
```

可通过 `osuIrc.sendStartupMessage` 关闭这条启动消息，IRC 本身仍然必须启用。

## Web 队列页面

默认地址：

```text
http://127.0.0.1:24051/
```

页面显示：

- tosu 连接状态、osu! 当前谱面和游戏状态。
- 等待中、处理中、已发送、失败的点歌记录。
- bilibili 用户头像和用户名。
- 当前谱面、非当前谱面或尚未判断标记。
- OBS Overlay 实时预览、完整 URL 和一键复制按钮。

关闭 tosu 时页面会显示“tosu 已停用”；弹幕监听、谱面查询和 IRC 转发仍然正常。

## OBS Overlay

在 OBS 中添加“浏览器”来源：

```text
http://127.0.0.1:24051/overlay
```

推荐分辨率：`760 × 100`。不需要自定义 CSS。

Overlay 只有一行：左侧是当前点歌者头像；上方小字显示用户名和“队列 X 人”；队列人数后显示最多 5 个后续用户头像，更多时显示 `+N`；中间分隔线用于区分当前点歌者与后续队列。主标题显示 Artist/Title，难度名以小字放在标题下方。无人点歌时完全透明。

队列规则：

- 新点歌只进入后续队列，不会覆盖当前项。
- 尚未游玩且未选中同谱时，当前项默认保留 300 秒。
- tosu 检测到已经选中完全相同谱面但尚未开始时，从匹配开始保留 120 秒。
- 检测到 `play` 且谱面匹配后，当前项锁定显示。
- 游玩结束后仍保留；切换到其它谱面时立即进入下一首，如果一直没有切谱面则在 60 秒后自动推进。
- 如果主播跳过当前项、直接游玩队列中另一首点歌，实际正在游玩的点歌会立即提升为当前项；被跳过项移出 Overlay，其它候场项保留原顺序。
- 关闭 tosu 后无法自动识别开始/结束游玩，Overlay 使用普通 300 秒轮换。

## 配置字段说明

通常使用 Web 设置向导即可完成配置；以下字段说明主要用于手动修改 `config.json`。

### bilibili

- `roomId`：直播间号，必须大于 0。
- `sessdata`：bilibili 登录 Cookie。留空可匿名监听，但用户名可能显示为 `M***`。

### osuIrc

- `server`：IRC 服务器，默认 `irc.ppy.sh:6667`，即 osu! 官方 Bancho IRC。兼容相同登录与私聊协议的私服玩家可改为自己的 `主机名:端口`；当前仅支持非 TLS 的普通 IRC 连接。
- `username`：发送点歌的 osu! 账号用户名。
- `password`：osu! IRC 专用密码。
- `targetUsername`：游戏内接收私聊点歌的用户名。
- `sendIntervalSeconds`：IRC 消息最小发送间隔，不能低于 0.5 秒。
- `sendStartupMessage`：是否发送启动成功消息。

### osuApi

- `enabled`：是否通过 API 获取谱面资料、难度信息和 Mods 后星数。Web 向导首次运行默认勾选。
- `clientId`、`clientSecret`：osu! OAuth 应用凭据，必须同时填写。

### chat

- `requestKeywords`：可识别的点歌前缀数组。纯数字、`b/` 和 `s/` 不依赖关键词。

### tosu

- `enabled`：是否启用 tosu。开启后同步当前谱面、匹配状态和 Overlay 游玩流程。
- `url`：tosu v2 JSON 地址，默认 `http://127.0.0.1:24050/json/v2`。
- `pollIntervalSeconds`：轮询间隔，最低 0.25 秒，默认 1 秒。

tosu 使用独立本机直连，不经过 `network.proxy`。

### display

- `useUnicodeIrc`：IRC 推送是否优先 Unicode，默认 `false`，即普通 Artist/Title。
- `useUnicodeWeb`：Web 队列是否优先 Unicode，默认 `true`。
- `useUnicodeOverlay`：OBS Overlay 是否优先 Unicode，默认 `true`。
- 所选字段为空时自动回退另一套字段，因此老谱面不会显示空歌名。

### web

- `port`：队列页面和 Overlay 的本机端口。
- `overlayHoldSeconds`：未游玩、未选中同谱时的保留时间，默认 300 秒。
- `overlayMatchedHoldSeconds`：已选中同谱但没有开始时的保留时间，默认 120 秒。
- `overlayPlayedHoldSeconds`：游玩结束后仍停留在同一谱面时的兜底保留时间，默认 60 秒；若切换到其它谱面会立即推进。

三个保留时间允许 `0–3600`。从旧版默认 120/500 秒配置升级、且尚未出现 `display` 区块时，会自动迁移为 300 秒。

### limits

- `userCooldownSeconds`：同一 bilibili 用户两次点歌的最小间隔，默认 30 秒。
- `mapDedupeSeconds`：同一谱面禁止重复点歌的时间，默认 600 秒，作用于所有用户。
- `queueMaxSize`：程序内部尚未处理请求的最大积压数量，默认 50。

冷却和去重可以设为 `0` 关闭。

### network

- `proxy`：留空表示直连。
- Clash 常见写法：`http://127.0.0.1:7890`。
- 支持带认证的 `http://用户名:密码@主机:端口`。

代理用于 bilibili 登录与弹幕、osu! 页面/API 和 Bancho IRC；IRC 通过 HTTP CONNECT 隧道连接。

### blacklist

- `userIds`：bilibili UID 字符串数组，优先推荐。
- `usernames`：用户名数组，区分依据为完整用户名的大小写无关匹配。

### logLevel

支持 `DEBUG`、`INFO`、`WARNING`、`ERROR`。日志保存在 `logs/bridge.log`，单文件最大 2 MB，保留 3 个旧文件。

## 常见问题

### 用户名为什么显示 M***？

bilibili 会限制匿名连接读取他人完整昵称。关闭程序并运行 `configure.bat`，在设置向导中使用手机客户端二维码登录，然后保存并重新启动程序。

### 不使用 tosu 可以点歌吗？

可以。关闭 `tosu.enabled` 只会停用当前谱面判断和基于 `play/selectPlay` 的 Overlay 自动同步，不影响弹幕、谱面查询、下载链接和 IRC 转发。

### 无法连接 bilibili、osu! API 或 Bancho IRC 怎么办？

先查看程序窗口或 `logs/bridge.log`，确认失败的是 bilibili、osu! API 还是 Bancho IRC，然后按以下顺序检查：

1. 确认系统时间正确，并检查其它程序能否正常访问对应网站。
2. 打开 `C:\Windows\System32\drivers\etc\hosts`，删除已经失效或来源不明的 bilibili、`ppy.sh`、`osu.ppy.sh`、`irc.ppy.sh`、`cho.ppy.sh` 固定 IP 记录；修改后运行 `ipconfig /flushdns`。
3. 在 Windows 防火墙和安全软件中允许 `osu-BiliRequest.exe` 联网。只建议临时关闭防护进行排查，不要长期停用防火墙。
4. Bancho IRC 使用 TCP 6667 端口。可在 PowerShell 运行 `Test-NetConnection irc.ppy.sh -Port 6667`；`ping` 成功并不代表该端口可以连接。
5. 检查路由器、校园网、公司网络或运营商是否限制连接。可临时改用手机热点测试，以判断问题来自电脑还是当前网络。
6. 仍无法直连时，在 Web 设置向导的“HTTP 代理”中填写可用代理，例如 Clash 常用的 `http://127.0.0.1:7890`，保存并重启程序。代理需要支持 HTTPS 和 HTTP CONNECT，才能同时用于 bilibili、osu! API 与 Bancho IRC。

如果配置代理后反而无法连接，请确认代理程序正在运行、端口填写正确，并检查代理软件是否允许本机连接。tosu 使用本机直连，不经过这里的代理。

### 为什么看到 unknown cmd？

程序已经忽略 `LOG_IN_NOTICE`、`WATCHED_CHANGE`、`ENTRY_EFFECT_MUST_RECEIVE`、`ONLINE_RANK_V3`、`FLOW_REWARD_CARD` 和 `LIVE_ANI_RES_UPDATE` 等与点歌无关的直播事件。未来 bilibili 新增事件时可能出现新的 warning，一般不影响弹幕点歌。

## 源码运行

需要 Python 3.10 或更高版本：

```powershell
python -m pip install -r requirements.txt
python main.py --setup
python main.py
```

`python main.py --setup` 同样打开本地 Web 设置页。

## Third-Party Components

Live chat connectivity is based on [xfgryujk/blivedm](https://github.com/xfgryujk/blivedm), pinned to source revision `8727ca9f8340e9c1e20e473eb1757bffb56c66f6` under the MIT License. Notices and license texts for all other third-party components are available in `THIRD_PARTY_NOTICES.md` and `LICENSES/`.

## License

This project is licensed under the [MIT License](LICENSE). You may use, modify, distribute, and commercially use the software, provided that the copyright notice and license text are retained in copies or substantial portions. The software is provided “as is,” without warranty. Third-party components remain subject to their respective licenses.
