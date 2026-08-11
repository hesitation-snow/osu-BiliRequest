# Changelog

## 1.0.1 - 2026-08-11

- Add a configurable `osuIrc.server` endpoint with `irc.ppy.sh:6667` as the default and preserve compatibility with existing configurations.
- Rename the Sayobot links to `Sayobot Full` and `Sayobot NoVideo` for clearer differentiation.
- Remove the unavailable dashboard settings shortcut while retaining first-run setup and `configure.bat`.
- Rewrite the quick-start guide and add connection troubleshooting for Hosts overrides, DNS cache, firewalls, TCP port 6667 and HTTP proxies.

## 1.0.0 - 2026-08-11

- Listen for bilibili live chat beatmap requests and forward them through Bancho IRC.
- Support Beatmap IDs, Beatmapset IDs, configurable keywords, Mods and request limits.
- Add osu! API metadata and modded-star lookup with webpage fallback.
- Add bilibili QR login, HTTP proxy support and user blacklists.
- Add the local queue dashboard, tosu synchronization and OBS Overlay.
- Add Unicode metadata preferences for IRC, Web and Overlay.
- Add queue promotion when a later request is played and post-play switch detection.
- Reject confirmed missing beatmaps without sending invalid IRC links; preserve the basic-link fallback for temporary lookup failures.
- Add Windows one-file builds, Web setup and third-party license notices.
