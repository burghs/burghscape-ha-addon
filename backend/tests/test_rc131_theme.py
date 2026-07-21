import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))

from routers.portal import CHANGE_PASSWORD_HTML, GETTING_STARTED_HTML, LOGIN_HTML, PORTAL_HTML


class DefaultValues(dict):
    def __missing__(self, key):
        return "value"


class RC131ThemeTests(unittest.TestCase):
    def test_client_portal_template_formats_with_theme_markup(self):
        rendered = PORTAL_HTML.format_map(DefaultValues())
        self.assertIn('data-theme-enabled', rendered)
        self.assertIn('/static/theme.js', rendered)
        self.assertIn('data-theme-choice="system"', rendered)
        self.assertIn('data-theme-choice="light"', rendered)
        self.assertIn('data-theme-choice="dark"', rendered)

    def test_authenticated_client_templates_share_theme_assets(self):
        self.assertIn('/static/theme.js', GETTING_STARTED_HTML)
        self.assertIn('/static/theme.css', GETTING_STARTED_HTML)
        self.assertIn('/static/theme.js', CHANGE_PASSWORD_HTML)
        self.assertIn('/static/theme.css', CHANGE_PASSWORD_HTML)

    def test_client_login_template_is_unchanged_by_theme(self):
        self.assertNotIn('/static/theme.js', LOGIN_HTML)
        self.assertNotIn('/static/theme.css', LOGIN_HTML)
        self.assertNotIn('data-theme-choice', LOGIN_HTML)

    def test_management_login_has_no_control_and_bootstrap_is_scoped(self):
        login = (ROOT / 'frontend/src/pages/Login.jsx').read_text()
        index = (ROOT / 'frontend/index.html').read_text()
        self.assertNotIn('ThemeControl', login)
        self.assertIn('location.pathname !== "/"', index)
        self.assertIn('!location.pathname.startsWith("/login")', index)

    def test_shared_key_and_theme_coverage(self):
        helper = (APP / 'static/theme.js').read_text()
        css = (APP / 'static/theme.css').read_text()
        control = (ROOT / 'frontend/src/components/ThemeControl.jsx').read_text()
        self.assertIn('"mybeacon-theme"', helper)
        self.assertIn('data-theme-choice', PORTAL_HTML)
        self.assertIn('role="radio"', control)
        for selector in ('portal-sidebar', 'app-card', 'form-input', 'table-head', 'modal-backdrop',
                         'badge-warning', 'progress-track', 'btn-danger', ':focus-visible'):
            self.assertIn(selector, css)


if __name__ == '__main__':
    unittest.main()
