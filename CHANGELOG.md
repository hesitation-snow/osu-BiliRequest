# Changelog

## 1.1.0 - 2026-08-12

- Add smooth Overlay slide-in and slide-out transitions when requests appear, finish or switch, and show difficulty, duration and star rating beside each request.
- Restore the live `/settings` page and add Settings and one-click application restart buttons to the queue dashboard.
- Make IRC forwarding optional while keeping it enabled by default, expose the custom IRC server in Web settings, and keep Web/Overlay queues operational without IRC.
- Replace username blacklisting with `blacklist.beatmapIds`, defaulting to `666`, while retaining bilibili UID and QQ OpenID blacklisting.
- Add QQ slash-menu compatible `/list`, linked `/np`, formatted `/help`, and private `/skip [index]` commands while preserving the legacy `!` aliases.
- Add `/ownerid` setup and configured streamer OpenIDs, allowing requesters to skip their own songs and streamers to skip any queue item in private or group chat.
- Stop after an osu! API definitive not-found response instead of repeating the same lookup through the website; temporary API failures still use the webpage fallback.
- Add a return-to-dashboard button to `/settings`, simplify its QQ instructions, and standardize user-facing beatmap/beatmapset capitalization.
- Display `群友` when QQ omits profile data and use each requested beatmapset's osu! cover as the QQ Overlay avatar without exposing QQ numbers or OpenIDs.
- Label the two mirror links as `Sayobot:[Full]~[NoVideo]`.
- Replace the application artwork with a tighter high-resolution source and include a 256px Windows icon frame for Explorer large-icon views.
- Add optional QQ official-bot song requests for group mentions and C2C messages through the official Access Token and WebSocket Gateway APIs.
- Add QQ AppID, AppSecret and optional group OpenID allowlist fields to `config.json` and the Web setup wizard.
- Normalize bilibili and QQ messages into one shared request pipeline, including platform-scoped cooldown identities, blacklist checks, queue state, IRC forwarding and Overlay output.
- Add QQ heartbeat, session resume, reconnect and duplicate-message handling without adding a new runtime dependency.
- Accept direct official osu! beatmap and beatmapset URLs from QQ group mentions and private messages while retaining bilibili's existing no-link parser behavior.
- Add the official osu-BiliRequest PNG artwork and embed its multi-resolution Windows icon in packaged executables.

## 1.0.1 - 2026-08-11

- Add a configurable `osuIrc.server` endpoint with `irc.ppy.sh:6667` as the default and preserve compatibility with existing configurations.
- Rename the Sayobot links to `Sayobot Full` and `Sayobot NoVideo` for clearer differentiation.
- Remove the unavailable dashboard settings shortcut while retaining first-run setup and `configure.bat`.
- Rewrite the quick-start guide and add connection troubleshooting for Hosts overrides, DNS cache, firewalls, TCP port 6667 and HTTP proxies.

## 1.0.0 - 2026-08-11

- Listen for bilibili live chat beatmap requests and forward them through Bancho IRC.
- Support beatmap IDs, beatmapset IDs, configurable keywords, Mods and request limits.
- Add osu! API metadata and modded-star lookup with webpage fallback.
- Add bilibili QR login, HTTP proxy support and user blacklists.
- Add the local queue dashboard, tosu synchronization and OBS Overlay.
- Add Unicode metadata preferences for IRC, Web and Overlay.
- Add queue promotion when a later request is played and post-play switch detection.
- Reject confirmed missing beatmaps without sending invalid IRC links; preserve the basic-link fallback for temporary lookup failures.
- Add Windows one-file builds, Web setup and third-party license notices.
