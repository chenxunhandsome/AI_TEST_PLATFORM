import os

from selenium import webdriver

from .playwright_engine import PlaywrightTestEngine, async_playwright, logger as playwright_logger
from .selenium_engine import (
    SeleniumTestEngine,
    get_chromium_browser_arguments,
    get_chromium_browser_prefs,
    logger as selenium_logger,
)


def _chromium_playwright_args():
    return [
        '--disable-blink-features=AutomationControlled',
        '--ignore-certificate-errors',
        '--allow-insecure-localhost',
        '--disable-web-security',
        '--disable-translate',
        '--disable-features=Translate,TranslateUI',
        '--lang=zh-CN',
    ]


async def _patched_playwright_start(self):
    try:
        self.playwright = await async_playwright().start()

        if self.browser_type == 'chromium':
            browser_launcher = self.playwright.chromium
        elif self.browser_type == 'firefox':
            browser_launcher = self.playwright.firefox
        elif self.browser_type == 'webkit':
            browser_launcher = self.playwright.webkit
        else:
            browser_launcher = self.playwright.chromium

        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--ignore-certificate-errors',
            '--allow-insecure-localhost',
            '--disable-web-security',
        ]
        if self.browser_type == 'chromium':
            launch_args = _chromium_playwright_args()

        self.browser = await browser_launcher.launch(
            headless=self.headless,
            args=launch_args,
        )

        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'locale': 'zh-CN',
        }
        if self.browser_type == 'chromium':
            context_options['extra_http_headers'] = {
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
            }

        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
        playwright_logger.info(f"Browser started: {self.browser_type}, headless={self.headless}")
    except Exception as e:
        playwright_logger.error(f"Browser start failed: {str(e)}")
        raise


def _build_chromium_selenium_options(options_factory, headless):
    options = options_factory()
    if headless:
        options.add_argument('--headless')
    for argument in get_chromium_browser_arguments():
        options.add_argument(argument)
    options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option('prefs', get_chromium_browser_prefs())
    return options


def _patched_selenium_start(self):
    try:
        os.environ['WDM_LOG_LEVEL'] = '0'
        os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

        is_available, error_msg = self.check_browser_available(self.browser_type)
        if not is_available:
            selenium_logger.error(f"Browser unavailable: {error_msg}")
            install_tips = {
                'chrome': 'brew install --cask google-chrome',
                'firefox': 'brew install --cask firefox',
                'edge': 'brew install --cask microsoft-edge',
            }
            tip = install_tips.get(self.browser_type, '')
            full_error = f"{error_msg}\n\n馃挕 瀹夎鍛戒护锛坢acOS锛夛細{tip}" if tip else error_msg
            raise Exception(full_error)

        if self.browser_type == 'chrome':
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            options = _build_chromium_selenium_options(Options, self.headless)
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        elif self.browser_type == 'firefox':
            from selenium.webdriver.firefox.options import Options
            from selenium.webdriver.firefox.service import Service
            from webdriver_manager.firefox import GeckoDriverManager

            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--width=1920')
            options.add_argument('--height=1080')
            options.set_preference('browser.cache.disk.enable', False)
            options.set_preference('browser.cache.memory.enable', True)
            options.set_preference('browser.cache.offline.enable', False)
            options.set_preference('network.http.use-cache', False)
            options.set_preference('browser.startup.homepage', 'about:blank')
            options.set_preference('startup.homepage_welcome_url', 'about:blank')
            options.set_preference('startup.homepage_welcome_url.additional', 'about:blank')
            options.set_preference('app.update.auto', False)
            options.set_preference('app.update.enabled', False)
            options.set_preference('extensions.update.enabled', False)
            options.set_preference('extensions.update.autoUpdateDefault', False)
            self.driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)

        elif self.browser_type == 'edge':
            from selenium.webdriver.edge.options import Options
            from selenium.webdriver.edge.service import Service
            from webdriver_manager.microsoft import EdgeChromiumDriverManager

            options = _build_chromium_selenium_options(Options, self.headless)
            self.driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)

        elif self.browser_type == 'safari':
            self.driver = webdriver.Safari()
            self.driver.set_window_size(1920, 1080)

        else:
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            options = _build_chromium_selenium_options(Options, self.headless)
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        self.driver.implicitly_wait(3)
        selenium_logger.info(f"Browser started: {self.browser_type}, headless={self.headless}")
    except Exception as e:
        selenium_logger.error(f"Browser start failed: {str(e)}")
        raise


PlaywrightTestEngine.start = _patched_playwright_start
SeleniumTestEngine.start = _patched_selenium_start
