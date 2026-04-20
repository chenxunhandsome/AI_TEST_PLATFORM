from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from apps.ui_automation.browser_config import (
    DEFAULT_BROWSER_HEIGHT,
    DEFAULT_BROWSER_WIDTH,
    get_default_chromium_window_size_argument,
)
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
        self.assertIn(get_default_chromium_window_size_argument(), arguments)
        self.assertFalse(prefs['translate.enabled'])
        self.assertFalse(prefs['translate']['enabled'])
        self.assertEqual(prefs['intl.accept_languages'], 'zh-CN,zh,en-US,en')

    def test_selenium_chromium_configuration_uses_custom_resolution_when_provided(self):
        arguments = get_chromium_browser_arguments(browser_width=1366, browser_height=768)

        self.assertIn('--window-size=1366,768', arguments)


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

        with patch('apps.ui_automation.playwright_engine.async_playwright', return_value=FakeAsyncPlaywrightFactory()):
            await engine.start()

        self.assertTrue(launch_call['headless'])
        self.assertIn('--disable-translate', launch_call['args'])
        self.assertIn('--disable-features=Translate,TranslateUI', launch_call['args'])
        self.assertIn(get_default_chromium_window_size_argument(), launch_call['args'])
        self.assertEqual(context_call['locale'], 'zh-CN')
        self.assertEqual(context_call['viewport']['width'], DEFAULT_BROWSER_WIDTH)
        self.assertEqual(context_call['viewport']['height'], DEFAULT_BROWSER_HEIGHT)
        self.assertEqual(context_call['screen']['width'], DEFAULT_BROWSER_WIDTH)
        self.assertEqual(context_call['screen']['height'], DEFAULT_BROWSER_HEIGHT)
        self.assertEqual(
            context_call['extra_http_headers']['Accept-Language'],
            'zh-CN,zh;q=0.9,en;q=0.8'
        )

    async def test_playwright_start_uses_custom_resolution_when_provided(self):
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

        engine = PlaywrightTestEngine(
            browser_type='chromium',
            headless=True,
            browser_width=1366,
            browser_height=768,
        )

        with patch('apps.ui_automation.playwright_engine.async_playwright', return_value=FakeAsyncPlaywrightFactory()):
            await engine.start()

        self.assertIn('--window-size=1366,768', launch_call['args'])
        self.assertEqual(context_call['viewport']['width'], 1366)
        self.assertEqual(context_call['viewport']['height'], 768)
        self.assertEqual(context_call['screen']['width'], 1366)
        self.assertEqual(context_call['screen']['height'], 768)
