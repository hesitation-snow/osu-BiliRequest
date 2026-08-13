import unittest
from pathlib import Path


class TosuOverlayPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = (
            Path(__file__).resolve().parents[1]
            / "tosu-overlay"
            / "osu-BiliRequest"
        )

    def test_package_has_tosu_metadata_and_entrypoint(self):
        metadata = (self.root / "metadata.txt").read_text(encoding="utf-8")
        html = (self.root / "index.html").read_text(encoding="utf-8")

        self.assertIn("Name: osu-BiliRequest", metadata)
        self.assertIn("CompatibleWith: tosu", metadata)
        self.assertIn("Resolution: 760x100", metadata)
        self.assertIn('src="./main.js"', html)
        self.assertIn('href="./main.css"', html)

    def test_script_connects_both_websockets_and_reconnects(self):
        script = (self.root / "main.js").read_text(encoding="utf-8")

        self.assertIn("/api/v1/ws", script)
        self.assertIn("/websocket/v2", script)
        self.assertIn("bridgePort", script)
        self.assertIn("setTimeout(open, retry)", script)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)

    def test_styles_keep_empty_overlay_transparent_and_animate(self):
        css = (self.root / "main.css").read_text(encoding="utf-8")

        self.assertIn("background: transparent", css)
        self.assertIn(".request-card.entering", css)
        self.assertIn(".request-card.leaving", css)
        self.assertIn("--animation-time", css)


if __name__ == "__main__":
    unittest.main()
