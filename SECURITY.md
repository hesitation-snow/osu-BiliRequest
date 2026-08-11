# Security policy

## Reporting a vulnerability

Please use GitHub's private security advisory feature instead of opening a public issue. Include the affected version, reproduction steps and possible impact. Do not include real cookies, passwords or OAuth secrets.

## Credential safety

`config.json` can contain a bilibili SESSDATA cookie, an osu! IRC password and an osu! OAuth Client Secret. It is intentionally excluded by `.gitignore` and release archives. Never commit or publicly share it.

If a configuration file is exposed:

1. Sign out affected bilibili sessions to invalidate the leaked SESSDATA.
2. Regenerate the osu! IRC password.
3. Rotate the osu! OAuth Client Secret.
4. Remove the leaked file from Git history; deleting only the latest copy is not sufficient.

The dashboard, setup page and Overlay listen on `127.0.0.1` only. Do not expose them through a public reverse proxy without adding authentication.
