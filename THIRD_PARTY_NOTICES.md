# Third-party notices

This project uses `blivedm` by xfgryujk:

- Repository: https://github.com/xfgryujk/blivedm
- Commit: `8727ca9f8340e9c1e20e473eb1757bffb56c66f6`
- License: MIT License

The connection and reconnect approach was reviewed against `blivechat` by xfgryujk:

- Repository: https://github.com/xfgryujk/blivechat
- Branch reviewed: `dev`
- License: MIT License

The Bilibili QR login flow was reviewed against `bilibili_live_stream_code` by ChaceQC:

- Repository: https://github.com/ChaceQC/bilibili_live_stream_code
- Commit reviewed: `51572bcf76affc1605955b296a794bfa8b04417c`
- License: Apache License 2.0

QR image generation uses `qrcode` 8.2 and Pillow 12.3.0:

- qrcode: https://github.com/lincolnloop/python-qrcode — BSD License
- Pillow: https://python-pillow.github.io/ — HPND License

Runtime networking and protocol dependencies:

- `aiohttp` 3.9.5 — Apache License 2.0
- `Brotli` 1.1.x — MIT License
- `pure-protobuf` 3.1.x — MIT License
- `yarl` 1.9.x — Apache License 2.0

Transitive packages used by the above dependencies include `aiosignal` (Apache-2.0), `attrs` (MIT), `frozenlist` (Apache-2.0), `multidict` (Apache-2.0), `idna` (BSD-3-Clause), `colorama` (BSD-3-Clause) and `typing-extensions` (PSF-2.0). Their upstream license and copyright notices remain applicable.

Windows executables are built with PyInstaller 6.20.0. PyInstaller is GPL-2.0-or-later with a special exception that permits using its bootloader to build and distribute programs under other licenses, including commercial programs.

Copyright notices and full license texts are retained in `LICENSES/`. The project's own source code is licensed separately under the root `LICENSE` file.
