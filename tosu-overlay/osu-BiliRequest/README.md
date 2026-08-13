# osu-BiliRequest tosu Overlay

## 安装

1. 保持 `osu-BiliRequest` 整个文件夹名称和内部结构不变。
2. 把该文件夹复制到 tosu 的 `static` 目录。
3. 同时启动 tosu 与 osu-BiliRequest。
4. 在 tosu 的 Overlay 列表中打开 `osu-BiliRequest`，或把插件页面添加到 OBS。

默认分辨率为 `760 × 100`。无人点歌时页面完全透明。

## 连接

插件会同时连接：

- tosu：`ws://127.0.0.1:24050/websocket/v2`
- osu-BiliRequest：`ws://127.0.0.1:24051/api/v1/ws`

两个连接都支持自动重连。若 osu-BiliRequest 的 Web 端口不是 `24051`，在 Overlay URL 后添加：

```text
?bridgePort=你的端口
```

显示连接诊断信息：

```text
?debug=1
```

多个参数可以用 `&` 连接，例如 `?bridgePort=25051&debug=1`。

## 自定义

- 在 `main.css` 顶部修改颜色、尺寸和动画时间。
- 在 `index.html` 调整卡片结构。
- 在 `main.js` 的 `updateCard()` 中选择和组合 API 字段。
- osu-BiliRequest 的完整接口说明位于 `http://127.0.0.1:24051/api`。

插件不读取 `config.json`，也不会取得 Cookie、IRC 密码或 OAuth Secret。
