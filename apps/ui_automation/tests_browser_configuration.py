from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from apps.ui_automation.playwright_engine import PlaywrightTestEngine
from apps.ui_automation.selenium_engine import (
    get_chromium_browser_arguments,
    get_chromium_browser_prefs,
)


class ChromiumBrowserConfigurationTests(TestCase):
    def test_selenium_chromium_configuration_disables_translate_prompt(self):
        arguments = get_chromium_browser_arguments()
        prefs = get_chromium_browser_prefs()

        self.assertIn('--disable-translate', arguments)
        self.assertTrue(any(arg.startswith('--disable-features=') and 'Translate' in arg for arg in arguments))
        self.assertIn('--lang=zh-CN', arguments)
        self.assertFalse(prefs['translate.enabled'])
        self.assertFalse(prefs['translate']['enabled'])
        self.assertEqual(prefs['intl.accept_languages'], 'zh-CN,zh,en-US,en')


class PlaywrightBrowserConfigurationTests(IsolatedAsyncioTestCase):
    async def test_playwright_start_uses_translate_suppression_for_chromium(self):
        launch_call = {}
        context_call = {}

        class FakePage:
            pass

        class FakeContext:
            async def new_page(self):
                return FakePage()

        class FakeBrowser:
            async def new_context(self, **kwargs):
                context_call.update(kwargs)
                return FakeContext()

        class FakeLauncher:
            async def launch(self, *, headless, args):
                launch_call['headless'] = headless
                launch_call['args'] = list(args)
                return FakeBrowser()

        class FakePlaywright:
            def __init__(self):
                self.chromium = FakeLauncher()
                self.firefox = FakeLauncher()
                self.webkit = FakeLauncher()

        class FakeAsyncPlaywrightFactory:
            async def start(self):
                return FakePlaywright()

        engine = PlaywrightTestEngine(browser_type='chromium', headless=True)

        with patch('apps.ui_automation.async_playwright', return_value=FakeAsyncPlaywrightFactory()):
            await engine.start()

        self.assertTrue(launch_call['headless'])
        self.assertIn('--disable-translate', launch_call['args'])
        self.assertIn('--disable-features=Translate,TranslateUI', launch_call['args'])
        self.assertEqual(context_call['locale'], 'zh-CN')
        self.assertEqual(
            context_call['extra_http_headers']['Accept-Language'],
            'zh-CN,zh;q=0.9,en;q=0.8'
        )
