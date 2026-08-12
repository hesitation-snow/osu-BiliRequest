# 连接与故障排查

## bilibili 用户名显示为 M***

bilibili 会限制匿名连接读取其他用户的完整昵称。打开设置页，使用 bilibili 手机客户端扫码登录，保存并重启程序。

## QQ 群消息没有反应

- 群聊消息需要先 `@机器人`，推荐直接发送 osu! 谱面链接。
- 确认机器人已加入目标群并启用了群聊事件权限。
- 如果配置了 `allowedGroupOpenids`，确认目标群 OpenID 已加入列表。
- 查看日志中是否出现“QQ 官方机器人已连接”。

## bilibili、osu! API 或 IRC 无法连接

1. 查看程序窗口或 `logs/bridge.log`，确认失败的服务。
2. 检查系统时间，确认其它程序能正常访问对应网站。
3. 检查 `C:\Windows\System32\drivers\etc\hosts`，删除失效或来源不明的 bilibili、`ppy.sh`、`osu.ppy.sh`、`irc.ppy.sh`、`cho.ppy.sh` 固定 IP；然后运行 `ipconfig /flushdns`。
4. 在 Windows 防火墙和安全软件中允许 `osu-BiliRequest.exe` 联网。
5. 尝试手机热点，排除路由器、校园网、公司网络或运营商限制。
6. 仍无法直连时，在设置页填写 HTTP 代理，例如 `http://127.0.0.1:7890`，保存并重启。

如果填写代理后无法连接，确认代理程序正在运行、端口正确，并允许本机连接。代理需要支持 HTTPS 和 HTTP CONNECT。tosu 使用本机直连，不经过代理。

## IRC 可以 ping，但程序连接超时

`ping` 只测试 ICMP，不代表 TCP 6667 端口可用。请在 PowerShell 运行：

```powershell
Test-NetConnection irc.ppy.sh -Port 6667 -InformationLevel Detailed
```

只有 `TcpTestSucceeded: True` 才说明 IRC 端口可连接。若域名解析到手动指定的旧 IP，请检查 Hosts 文件。

## Windows 证书库警告

程序会屏蔽 Windows 证书库中单条异常证书产生的已知警告。真正导致连接失败的 HTTPS/TLS 错误仍会写入日志。

## unknown cmd 警告

程序已过滤多种与点歌无关的 bilibili 直播事件。未来 bilibili 新增事件时仍可能出现新的 `unknown cmd` warning；如果弹幕点歌正常，通常可以忽略。

## 不使用 tosu 可以点歌吗

可以。关闭 tosu 只会停用当前谱面判断与 Overlay 自动推进，不影响消息监听、谱面查询、下载链接和 IRC 转发。
