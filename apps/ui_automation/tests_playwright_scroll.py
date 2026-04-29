import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from apps.ui_automation.playwright_engine import PlaywrightTestEngine


def make_scroll_step(payload):
    return SimpleNamespace(
        action_type='scroll',
        description='scroll',
        save_as='',
        input_value=json.dumps(payload, ensure_ascii=False),
        wait_time=1000,
        assert_type='',
        assert_value='',
    )


class FakeScrollPage:
    def __init__(self, url='http://example.com/menu'):
        self.url = url
        self._closed = False
        self.bring_to_front_calls = 0
        self.evaluate_calls = []

    def is_closed(self):
        return self._closed

    async def bring_to_front(self):
        self.bring_to_front_calls += 1

    async def evaluate(self, script, payload):
        self.evaluate_calls.append((script, payload))
        return {
            'label': 'div.virtually-menu-container',
            'eventTargetLabel': 'div.menu-item',
            'url': self.url,
            'beforeTop': 100,
            'afterTop': 545,
            'beforeLeft': 12,
            'afterLeft': 12,
        }


class FakeScrollContext:
    def __init__(self, pages):
        self.pages = pages


class PlaywrightScrollExecutionTests(IsolatedAsyncioTestCase):
    async def test_coordinate_scroll_uses_browser_side_scroll_target_resolution(self):
        engine = PlaywrightTestEngine()
        page = FakeScrollPage()
        engine.context = FakeScrollContext([page])
        engine.page = page

        step = make_scroll_step({
            'scroll_mode': 'coordinates',
            'scroll_scope': 'element',
            'scroll_direction': 'down',
            'start_x': 79,
            'start_y': 264,
            'target_x': 104,
            'target_y': 709,
        })

        success, log, screenshot = await engine.execute_step(step, {
            'name': '左侧菜单栏',
            'locator_strategy': 'xpath',
            'locator_value': "//div[@class='virtually-menu-container']",
        })

        self.assertTrue(success)
        self.assertIsNone(screenshot)
        self.assertEqual(page.bring_to_front_calls, 1)
        self.assertEqual(len(page.evaluate_calls), 1)
        self.assertEqual(page.evaluate_calls[0][1], [79, 264, 0, 445])
        self.assertIn('div.virtually-menu-container', log)
        self.assertIn('div.menu-item', log)
        self.assertIn('actual delta: (0, 445)', log)

    async def test_coordinate_scroll_rejects_zero_delta(self):
        engine = PlaywrightTestEngine()
        page = FakeScrollPage()
        engine.context = FakeScrollContext([page])
        engine.page = page

        step = make_scroll_step({
            'scroll_mode': 'coordinates',
            'scroll_scope': 'element',
            'scroll_direction': 'vertical',
            'start_x': 100,
            'start_y': 200,
            'target_x': 100,
            'target_y': 200,
        })

        success, log, screenshot = await engine.execute_step(step, {})

        self.assertFalse(success)
        self.assertIsNone(screenshot)
        self.assertEqual(page.evaluate_calls, [])
        self.assertIn('scroll delta is 0', log)
