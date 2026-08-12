# 点歌格式与过滤规则

## bilibili 弹幕

支持以下格式：

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

- 纯数字与 `b/` 表示 beatmap ID。
- `s/` 表示 beatmapset ID，程序会选择其中星数最高的难度。
- 点歌关键词可在设置页修改。
- bilibili 只处理符合格式的普通文字弹幕，夹杂其它聊天内容的消息不会进入点歌流程。

## QQ 消息

QQ 推荐直接发送 osu! 官方谱面链接，例如：

```text
https://osu.ppy.sh/beatmaps/5600294
https://osu.ppy.sh/beatmapsets/2533001#osu/5600294 +HD +DT
```

也支持纯数字、`b/ID`、`s/ID`、`/beatmaps/ID` 与 `/beatmapsets/ID#模式/难度ID`。群聊中需要先 `@机器人`，私聊可直接发送。

## Mods

支持 `HD`、`HR`、`DT`、`NC`、`HT` 等 Mods，可写成 `+HDDT`、`+HD +DT` 或 `HD DT`。重复 Mods 会合并，`DT+HT`、`NC+HT`、`EZ+HR` 等冲突组合会被拒绝。

配置 osu! API 后会查询 Mods 后的真实星数。没有 osu! API 或查询临时失败时，消息会显示原始星数；DT、NC 和 HT 仍会调整 BPM 与时长。

## 限流与黑名单

- `limits.userCooldownSeconds`：同一用户两次点歌之间的最短时间，默认 30 秒。
- `limits.mapDedupeSeconds`：同一谱面禁止重复点歌的时间，默认 600 秒。
- `limits.queueMaxSize`：等待处理请求的最大数量，默认 50。
- `blacklist.userIds`：屏蔽 bilibili UID 或 QQ OpenID。
- `blacklist.beatmapIds`：屏蔽指定数字对应的纯数字、`b/` 和 `s/` 请求。

默认谱面数字黑名单包含 `666`，用于避免常见聊天语气词误触。当前黑名单为精确匹配；如需屏蔽 `6666`、`66666` 等内容，需要分别添加。明确写成 `点歌 666`、`b/666` 或 `s/666` 的请求也会被同一黑名单拦截。
