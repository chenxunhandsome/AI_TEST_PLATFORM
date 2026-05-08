import json
from unittest import TestCase

from apps.ui_automation.playwright_engine import PlaywrightTestEngine
from apps.ui_automation.variable_resolver import parse_canvas_action_payload


class FakePage:
    def __init__(self, url):
        self.url = url

    def is_closed(self):
        return False


class FakeContext:
    def __init__(self, pages):
        self.pages = pages


class CanvasActionPayloadTests(TestCase):
    def test_parse_canvas_click_payload(self):
        payload = parse_canvas_action_payload(json.dumps({
            'mode': 'canvas',
            'action': 'click',
            'page_index': '1',
            'frame_selector': '#plt-workflow-iframe',
            'frame_url': 'workflow-modeler/index.html#/editor/demo',
            'x': '120',
            'y': 240,
            'hold_ms': '500',
            'steps': '15',
        }))

        self.assertEqual(payload['action'], 'click')
        self.assertEqual(payload['page_index'], 1)
        self.assertFalse(payload['lock_page_index'])
        self.assertEqual(payload['frame_selector'], '#plt-workflow-iframe')
        self.assertEqual(payload['x'], 120)
        self.assertEqual(payload['y'], 240)
        self.assertEqual(payload['hold_ms'], 500)
        self.assertEqual(payload['steps'], 15)

    def test_parse_canvas_drag_payload(self):
        payload = parse_canvas_action_payload(json.dumps({
            'mode': 'canvas',
            'action': 'drag',
            'active_page_index': 2,
            'start': {'x': 10, 'y': 20},
            'target': {'x': '300', 'y': '420'},
        }))

        self.assertEqual(payload['action'], 'drag')
        self.assertEqual(payload['active_page_index'], 2)
        self.assertFalse(payload['lock_page_index'])
        self.assertEqual(payload['frame_selector'], '#plt-workflow-iframe')
        self.assertEqual(payload['start'], {'x': 10, 'y': 20})
        self.assertEqual(payload['target'], {'x': 300, 'y': 420})

    def test_parse_canvas_lock_page_index(self):
        payload = parse_canvas_action_payload(json.dumps({
            'mode': 'canvas',
            'action': 'click',
            'page_index': 1,
            'lock_page_index': True,
            'x': 1,
            'y': 2,
        }))

        self.assertTrue(payload['lock_page_index'])

    def test_invalid_canvas_payload_returns_none(self):
        self.assertIsNone(parse_canvas_action_payload(''))
        self.assertIsNone(parse_canvas_action_payload('{"mode":"canvas","action":"click"}'))
        self.assertIsNone(parse_canvas_action_payload('{"mode":"canvas","action":"drag","start":{"x":1,"y":2}}'))


class CanvasRuntimePageTests(TestCase):
    def test_canvas_uses_current_page_when_saved_index_is_stale(self):
        original_page = FakePage('https://example.com/original')
        popup_page = FakePage('https://example.com/popup')
        engine = PlaywrightTestEngine()
        engine.context = FakeContext([original_page, popup_page])
        engine.page = popup_page

        selected_page = engine._get_canvas_runtime_page({
            'page_index': 0,
            'active_page_index': 0,
        })

        self.assertIs(selected_page, popup_page)

    def test_canvas_can_lock_to_saved_page_index_when_explicit(self):
        original_page = FakePage('https://example.com/original')
        popup_page = FakePage('https://example.com/popup')
        engine = PlaywrightTestEngine()
        engine.context = FakeContext([original_page, popup_page])
        engine.page = popup_page

        selected_page = engine._get_canvas_runtime_page({
            'page_index': 0,
            'lock_page_index': True,
        })

        self.assertIs(selected_page, original_page)
