# IRC 与 osu! API

## IRC 推送

默认服务器为 osu! Bancho IRC：`irc.ppy.sh:6667`。IRC 专用密码可在 [osu! Legacy API 设置](https://osu.ppy.sh/home/account/edit#Legacy_api) 获取。

成功读取谱面资料后，消息格式类似：

```text
[Miarru] -> [Ranked] [Zektbach - The Sealer 〜ア・ミリアとミリアの民〜 [921206025887's Extra]] (205 BPM, 6.11*, 2:03) Sayobot:[Full]~[NoVideo]
```

- `Full`：Sayobot 完整谱面包。
- `NoVideo`：Sayobot 无视频谱面包。
- 使用 DT、NC 或 HT 时，BPM 与时长会按速度调整。
- 启动成功消息可通过 `osuIrc.sendStartupMessage` 关闭。
- 不需要游戏内推送时可关闭 `osuIrc.enabled`，Web 与 Overlay 不受影响。

可以修改 `osuIrc.server` 连接兼容相同登录与私聊协议的私服 IRC。当前仅支持非 TLS 的普通 IRC。

## osu!lazer 注意事项

osu!lazer 无法在游戏内收到同一账号通过 Bancho IRC 发给自己的消息。请使用不同的 IRC 发送账号与游戏内接收账号，或使用 osu!stable 接收。

含空格的 osu! 用户名在 IRC 中需要使用下划线，例如 `peppy player` 写成 `peppy_player`。

## osu! API

在 [osu! OAuth 设置](https://osu.ppy.sh/home/account/edit#oauth) 创建 OAuth 应用，把 Client ID 和 Client Secret 填入设置页。

启用后程序会获取：

- Ranked Status、Artist、Title 与难度名。
- BPM、时长和原始星数。
- 指定 Mods 后的真实星数。

osu! API 明确返回谱面不存在时，程序会直接拒绝请求，不再重复查询网页；临时网络错误才会回退官方谱面页。API 与网页都暂时不可用时，会保留基础链接兜底。

纯数字默认按 beatmap ID 处理。如果输入的是 beatmapset ID，请使用 `s/数字`。
