import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main


class MainTests(unittest.TestCase):
    def test_first_run_opens_setup_then_starts_service(self):
        async def setup(config_path):
            Path(config_path).write_text("{}", encoding="utf-8")

        async def run_service(_config, _config_path):
            return None

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            config_path = base_dir / "config.json"
            resolved_config_path = config_path.resolve()
            config = SimpleNamespace(
                log_level="INFO",
                safe_summary=lambda: "test config",
            )
            args = argparse.Namespace(
                config=None,
                setup=False,
                check_config=False,
            )

            with (
                mock.patch.object(main, "parse_args", return_value=args),
                mock.patch.object(main, "app_directory", return_value=base_dir),
                mock.patch.object(main, "run_setup_web", side_effect=setup) as setup_mock,
                mock.patch.object(main.Config, "load", return_value=config) as load_mock,
                mock.patch.object(main, "configure_logging"),
                mock.patch.object(main, "run", side_effect=run_service) as run_mock,
            ):
                self.assertEqual(main.main(), 0)

            setup_mock.assert_awaited_once_with(resolved_config_path)
            load_mock.assert_called_once_with(resolved_config_path)
            run_mock.assert_awaited_once_with(config, resolved_config_path)

    def test_web_restart_launches_same_app_with_absolute_config(self):
        async def run_service(_config, _config_path):
            return True

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            config_path = (base_dir / "config.json").resolve()
            config_path.write_text("{}", encoding="utf-8")
            config = SimpleNamespace(
                log_level="INFO",
                safe_summary=lambda: "test config",
            )
            args = argparse.Namespace(
                config=config_path,
                setup=False,
                check_config=False,
            )

            with (
                mock.patch.object(main, "parse_args", return_value=args),
                mock.patch.object(main, "app_directory", return_value=base_dir),
                mock.patch.object(main.Config, "load", return_value=config),
                mock.patch.object(main, "configure_logging"),
                mock.patch.object(main, "run", side_effect=run_service),
                mock.patch.object(main.subprocess, "Popen") as popen,
            ):
                self.assertEqual(main.main(), 0)

            command = popen.call_args.args[0]
            self.assertEqual(command[-2:], ["--config", str(config_path)])
            self.assertEqual(popen.call_args.kwargs["cwd"], base_dir)


if __name__ == "__main__":
    unittest.main()
