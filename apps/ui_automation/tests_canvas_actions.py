import json
from unittest import TestCase

from apps.ui_automation.variable_resolver import parse_canvas_action_payload


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
        self.assertEqual(payload['frame_selector'], '#plt-workflow-iframe')
        self.assertEqual(payload['start'], {'x': 10, 'y': 20})
        self.assertEqual(payload['target'], {'x': 300, 'y': 420})

    def test_invalid_canvas_payload_returns_none(self):
        self.assertIsNone(parse_canvas_action_payload(''))
        self.assertIsNone(parse_canvas_action_payload('{"mode":"canvas","action":"click"}'))
        self.assertIsNone(parse_canvas_action_payload('{"mode":"canvas","action":"drag","start":{"x":1,"y":2}}'))
