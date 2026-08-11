from __future__ import annotations

import argparse
import asyncio
import logging
import logging.handlers
import sys
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message=r"Bad certificate in Windows certificate store:.*",
    category=UserWarning,
    module=r"ssl",
)

from bili_osu_bridge.app import run
from bili_osu_bridge import __version__
from bili_osu_bridge.config import Config
from bili_osu_bridge.setup_web import run_setup_web


def app_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_logging(base_dir: Path, level: str) -> None:
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "bridge.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        handlers=[console, file_handler],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="bilibili弹幕到 osu! IRC 点歌桥接")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, help="配置文件路径，默认使用程序旁的 config.json")
    parser.add_argument("--setup", action="store_true", help="在浏览器中填写或修改配置")
    parser.add_argument("--check-config", action="store_true", help="检查配置后退出")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = app_directory()
    config_path = (args.config or (base_dir / "config.json")).resolve()

    if args.setup:
        try:
            asyncio.run(run_setup_web(config_path))
        except KeyboardInterrupt:
            print("\n已取消 Web 设置。")
            return 2
        except Exception as exc:
            print(f"配置错误：{exc}")
            return 2
        return 0

    if not config_path.exists():
        print(f"首次运行，正在创建配置：{config_path}", flush=True)
        try:
            asyncio.run(run_setup_web(config_path))
        except KeyboardInterrupt:
            print("\n已取消 Web 设置。")
            return 2
        except Exception as exc:
            print(f"配置错误：{exc}")
            return 2

    try:
        config = Config.load(config_path)
    except Exception as exc:
        print(f"配置错误：{exc}")
        return 2

    configure_logging(base_dir, config.log_level)
    logging.getLogger(__name__).info("配置已加载：%s", config.safe_summary())
    if args.check_config:
        print("配置检查通过：" + config.safe_summary())
        return 0

    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("用户停止程序")
        return 0
    except Exception:
        logging.getLogger(__name__).exception("程序异常退出")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
