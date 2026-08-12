# osu-BiliRequest Wiki

这里保存 README 中省略的进阶说明。第一次使用请先阅读仓库根目录的 [README](https://github.com/hesitation-snow/osu-BiliRequest#readme)。

## 文档目录

- [点歌格式与过滤规则](https://github.com/hesitation-snow/osu-BiliRequest/wiki/Request‐Formats)
- [配置字段说明](https://github.com/hesitation-snow/osu-BiliRequest/wiki/Configuration)
- [QQ 官方机器人](https://github.com/hesitation-snow/osu-BiliRequest/wiki/QQ‐Bot)
- [IRC 与 osu! API](https://github.com/hesitation-snow/osu-BiliRequest/wiki/IRC‐and‐osu‐API)
- [Web、OBS Overlay 与 tosu](https://github.com/hesitation-snow/osu-BiliRequest/wiki/Overlay‐and‐tosu)
- [连接与故障排查](https://github.com/hesitation-snow/osu-BiliRequest/wiki/Troubleshooting)

## 本地地址

- Web 队列：`http://127.0.0.1:24051/`
- 设置页面：`http://127.0.0.1:24051/settings`
- OBS Overlay：`http://127.0.0.1:24051/overlay`

这些页面默认只监听 `127.0.0.1`，不会直接暴露到局域网或公网。

> 请勿公开分享 `config.json`。其中可能包含 bilibili Cookie、QQ AppSecret、IRC 密码和 osu! OAuth Client Secret。
