# osu-BiliRequest Wiki

这里保存 README 中省略的进阶说明。第一次使用请先阅读仓库根目录的 [README](../README.md)。

## 文档目录

- [点歌格式与过滤规则](Request-Formats.md)
- [配置字段说明](Configuration.md)
- [QQ 官方机器人](QQ-Bot.md)
- [IRC 与 osu! API](IRC-and-osu-API.md)
- [Web、OBS Overlay 与 tosu](Overlay-and-tosu.md)
- [连接与故障排查](Troubleshooting.md)

## 本地地址

- Web 队列：`http://127.0.0.1:24051/`
- 设置页面：`http://127.0.0.1:24051/settings`
- OBS Overlay：`http://127.0.0.1:24051/overlay`

这些页面默认只监听 `127.0.0.1`，不会直接暴露到局域网或公网。

> 请勿公开分享 `config.json`。其中可能包含 bilibili Cookie、QQ AppSecret、IRC 密码和 osu! OAuth Client Secret。
