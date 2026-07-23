import re
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from routers.portal import GETTING_STARTED_HTML


class GettingStartedUXTests(unittest.TestCase):
    def test_complete_stage_and_visual_inventory(self):
        self.assertEqual(len(re.findall(r'data-stage="\d+"', GETTING_STARTED_HTML)), 10)
        visual_ids = re.findall(r'data-image="([^"]+)"', GETTING_STARTED_HTML)
        self.assertEqual(len(visual_ids), 9)
        self.assertEqual(len(set(visual_ids)), 9)
        for visual_id in visual_ids:
            self.assertIn(repr(visual_id), GETTING_STARTED_HTML)
        self.assertNotIn("Placeholder for", GETTING_STARTED_HTML)
        self.assertNotIn("new Image()", GETTING_STARTED_HTML)

    def test_mobile_first_layout_contracts(self):
        for contract in (
            "overflow-x:hidden",
            "grid-template-columns:minmax(0,1fr)",
            "scroll-snap-type:x proximity",
            "position:sticky; bottom:0",
            "min-height:46px",
            "safe-area-inset-bottom",
            "font-size:clamp(",
            "list-style-position:outside",
        ):
            self.assertIn(contract, GETTING_STARTED_HTML)

    def test_accessibility_and_responsive_content_contracts(self):
        for contract in (
            'aria-label="Stage navigation"',
            "aria-current",
            "role', 'img",
            "mock-caption",
            "prefers-reduced-motion: reduce",
            "max-width:100%; height:auto",
            "overflow-x:auto; white-space:pre",
            "display:block; overflow-x:auto",
        ):
            self.assertIn(contract, GETTING_STARTED_HTML)

    def test_static_references_exist_and_images_have_alt_text(self):
        for source in re.findall(r'<(?:script|img)[^>]+src="([^"]+)"', GETTING_STARTED_HTML):
            if not source.startswith("/static/"):
                continue
            asset = APP / "static" / source.removeprefix("/static/")
            self.assertTrue(asset.is_file(), source)
        for tag in re.findall(r"<img\b[^>]*>", GETTING_STARTED_HTML):
            self.assertRegex(tag, r'alt="[^"]+"')

    def test_navigation_and_client_links_are_not_empty(self):
        for href in re.findall(r'href="([^"]*)"', GETTING_STARTED_HTML):
            self.assertTrue(href.strip())
        for control in ("prev-stage", "mark-stage", "next-stage", "current-stage-label"):
            self.assertIn(f'id="{control}"', GETTING_STARTED_HTML)


if __name__ == "__main__":
    unittest.main()
