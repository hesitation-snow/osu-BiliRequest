# Web、OBS Overlay 与 tosu

## Web 队列

默认地址：`http://127.0.0.1:24051/`

页面显示：

- tosu 连接状态、osu! 当前谱面和游戏状态。
- 等待、处理、已发送及失败的点歌记录。
- 点歌者头像、用户名与谱面资料。
- 当前谱面匹配结果。
- Overlay 预览、完整 URL 和复制按钮。
- 设置与重启软件按钮。

## OBS Overlay

在 OBS 添加“浏览器”来源，填写：

```text
http://127.0.0.1:24051/overlay
```

推荐分辨率为 `760 × 100`，无需自定义 CSS。

Overlay 显示当前点歌者头像、用户名、队列人数、后续点歌者头像、Artist/Title、难度名、时长与星数。新点歌会渐显并从右侧滑入，完成或切歌时渐隐并向左滑出；无人点歌时完全透明。

QQ 没有提供头像时，优先使用所点 beatmapset 的 osu! 封面。

## 自定义 Overlay API

打开 `http://127.0.0.1:24051/api` 可以查看本机接口说明。用户可自行制作 HTML/CSS/JavaScript 页面并在 OBS 中直接加载，不需要修改 osu-BiliRequest 源码。
仓库中的 `examples/custom-overlay.html` 是一个可编辑的 WebSocket 示例，可直接作为 OBS 本地文件来源使用；端口不是 24051 时，在文件 URL 后添加 `?port=端口`。

- `GET /api/v1/status`：完整队列、tosu 与 Overlay 状态。
- `GET /api/v1/overlay`：Overlay 常用数据的精简响应。
- `GET /api/v1/queue`：点歌记录与队列数量。
- `GET /api/v1/tosu`：主播当前 osu! 状态与谱面。
- `WS /api/v1/ws`：每秒推送一次完整状态。
- `GET /api/v1`：机器可读接口目录。

接口允许同源、本机网页及 `file://` 页面读取，不允许普通公网网页跨来源读取，也不会返回 config.json 中的 Cookie、密码或 Client Secret。旧的 `/api/status` 保留兼容。

```javascript
const data = await fetch('http://127.0.0.1:24051/api/v1/overlay')
  .then(response => response.json());
const current = data.overlay.current;
```

## tosu 自定义 Overlay 插件

Releases 中的 `osu-BiliRequest-tosu-overlay.zip` 是可直接安装的 tosu 静态插件：

1. 解压 ZIP。
2. 把完整的 `osu-BiliRequest` 文件夹复制到 tosu 的 `static` 目录。
3. 同时启动 tosu 和 osu-BiliRequest。
4. 从 tosu Overlay 列表打开 `osu-BiliRequest`，推荐分辨率为 `760 × 100`。

插件会同时连接两个本机 WebSocket：

```text
ws://127.0.0.1:24050/websocket/v2
ws://127.0.0.1:24051/api/v1/ws
```

tosu WebSocket 提供游戏状态和当前 beatmap，osu-BiliRequest WebSocket 提供点歌者、队列及 Overlay 状态。两个连接互不替代，并各自支持自动重连。

若 Web 端口不是 `24051`，在插件页面 URL 后添加 `?bridgePort=端口`。添加 `?debug=1` 可显示两个 WebSocket 的连接状态。用户可以在插件的 `main.css` 顶部修改颜色、尺寸和动画，也可以编辑 `main.js` 的 `updateCard()` 自由组合 API 字段。

## 队列推进规则

- 新点歌进入队尾，不覆盖当前项。
- 未游玩且没有选中同谱时，当前项默认保留 300 秒。
- tosu 检测到选中相同谱面但尚未开始时，从匹配开始保留 120 秒。
- 检测到 `play` 且谱面匹配后，当前项锁定显示。
- 游玩结束后，切换到其它谱面会立即进入下一首；一直没有切谱面则在 60 秒后推进。
- 主播直接游玩队列中的其它点歌时，该项目会提升为当前项，被跳过的当前项移出 Overlay，其它项目保持顺序。
- 关闭 tosu 后无法自动识别开始与结束游玩，Overlay 按普通 300 秒规则轮换。

这些时间可在设置页或 `config.json` 的 `web` 区块修改。

## tosu

默认读取：

```text
http://127.0.0.1:24050/json/v2
```

tosu 用于读取当前 beatmap 以及 `play`、`selectPlay` 状态。关闭 tosu 不影响 bilibili/QQ 消息监听、谱面查询、Web 队列或 IRC 转发。

tosu 始终通过本机直连，不使用 `network.proxy`。
