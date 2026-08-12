# 配置字段说明

一般使用 `http://127.0.0.1:24051/settings` 即可完成配置。以下内容用于需要手动修改 `config.json` 的情况。

## bilibili

- `roomId`：直播间号，必须大于 0。
- `sessdata`：bilibili 登录 Cookie。留空时匿名监听，用户名可能显示为 `M***`。

二维码登录成功后，SESSDATA 会在保存配置时写入 `config.json`，设置页不会回显 Cookie 内容。

## qq

- `enabled`：是否启用 QQ 官方机器人。
- `appId`、`appSecret`：在 [QQ 开放平台](https://q.qq.com/) 创建机器人后获得的凭据。
- `allowedGroupOpenids`：允许点歌的群 OpenID 数组；留空允许机器人能够接收消息的全部群，不影响私聊。
- `ownerOpenids`：主播 OpenID 数组。主播可跳过任意队列项目，普通点歌者只能跳过自己的项目。

## osuIrc

- `enabled`：是否通过 IRC 转发点歌，默认开启。关闭后 Web、Overlay 和消息监听仍可使用。
- `server`：默认 `irc.ppy.sh:6667`，也可填写兼容相同协议的私服 IRC 地址。
- `username`：发送点歌的 osu! 账号用户名。
- `password`：osu! IRC 专用密码。
- `targetUsername`：游戏内接收私聊点歌的用户名。
- `sendIntervalSeconds`：IRC 消息最小发送间隔，不能低于 0.5 秒。
- `sendStartupMessage`：启动后是否向接收者发送连接成功消息。

当前只支持非 TLS 的普通 IRC 连接。

## osuApi

- `enabled`：是否使用 osu! API 获取谱面资料和 Mods 后星数。
- `clientId`、`clientSecret`：osu! OAuth 应用凭据，必须同时填写。

## chat

- `requestKeywords`：bilibili 弹幕可识别的点歌前缀数组。纯数字、`b/` 和 `s/` 不依赖关键词。

## tosu

- `enabled`：是否同步 osu! 当前谱面与游玩状态。
- `url`：默认 `http://127.0.0.1:24050/json/v2`。
- `pollIntervalSeconds`：轮询间隔，最低 0.25 秒，默认 1 秒。

tosu 使用本机直连，不经过 HTTP 代理。

## display

- `useUnicodeIrc`：IRC 是否优先使用 Unicode Artist/Title，默认关闭。
- `useUnicodeWeb`：Web 是否优先使用 Unicode Artist/Title，默认开启。
- `useUnicodeOverlay`：Overlay 是否优先使用 Unicode Artist/Title，默认开启。

Unicode 字段为空时会自动回退普通 Artist/Title，兼容没有 Unicode 信息的老谱面。

## web

- `port`：Web 队列、设置页和 Overlay 使用的本机端口，默认 24051。
- `overlayHoldSeconds`：未游玩且未选中同谱时的保留时间，默认 300 秒。
- `overlayMatchedHoldSeconds`：已选中同谱但尚未开始游玩时的保留时间，默认 120 秒。
- `overlayPlayedHoldSeconds`：游玩结束但一直没有切谱面时的兜底保留时间，默认 60 秒。

## limits、network 与日志

- `limits.userCooldownSeconds`：单用户点歌冷却，默认 30 秒。
- `limits.mapDedupeSeconds`：同谱去重时间，默认 600 秒。
- `limits.queueMaxSize`：最大等待队列，默认 50。
- `network.proxy`：HTTP 代理；留空表示直连，Clash 常见写法为 `http://127.0.0.1:7890`。
- `logLevel`：支持 `DEBUG`、`INFO`、`WARNING`、`ERROR`。

代理用于 bilibili、QQ、osu! 页面/API 和 IRC；IRC 通过 HTTP CONNECT 隧道连接。日志保存于 `logs/bridge.log`，单文件最大 2 MB，并保留 3 个旧文件。
