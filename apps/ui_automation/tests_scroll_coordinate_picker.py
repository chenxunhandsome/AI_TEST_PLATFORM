from unittest import TestCase

from apps.ui_automation.scroll_coordinate_picker import (
    LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS,
    claim_local_scroll_coordinate_picker_task,
    create_local_scroll_coordinate_picker_session,
    report_local_scroll_coordinate_picker_task,
    request_local_scroll_coordinate_picker_pages,
    request_local_scroll_coordinate_picker_select_page,
)


class LocalScrollCoordinatePickerTaskTests(TestCase):
    def tearDown(self):
        LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.clear()

    def test_claim_select_page_task_includes_page_index(self):
        session = create_local_scroll_coordinate_picker_session(
            user_id=101,
            runner_id=202,
            base_url='http://example.com',
        )
        session['state'] = 'ready'

        try:
            request_local_scroll_coordinate_picker_select_page(session, 1, timeout=0.01)
        except TimeoutError:
            pass

        task = claim_local_scroll_coordinate_picker_task(101, 202)

        self.assertIsNotNone(task)
        self.assertEqual(task['task_type'], 'scroll_coordinate_picker')
        self.assertEqual(task['action'], 'select_page')
        self.assertEqual(task['page_index'], 1)

    def test_claim_list_pages_task_does_not_include_page_index(self):
        session = create_local_scroll_coordinate_picker_session(
            user_id=301,
            runner_id=402,
            base_url='http://example.com',
        )
        session['state'] = 'ready'

        try:
            request_local_scroll_coordinate_picker_pages(session, timeout=0.01)
        except TimeoutError:
            pass

        task = claim_local_scroll_coordinate_picker_task(301, 402)

        self.assertIsNotNone(task)
        self.assertEqual(task['action'], 'list_pages')
        self.assertIsNone(task['page_index'])

    def test_report_start_success_preserves_start_payload(self):
        session = create_local_scroll_coordinate_picker_session(
            user_id=501,
            runner_id=602,
            base_url='http://example.com',
        )

        report_local_scroll_coordinate_picker_task(
            501,
            602,
            session['session_id'],
            'start',
            True,
            payload={
                'url': 'http://example.com/#/',
                'navigation_error': 'timeout',
            },
        )

        self.assertEqual(session['state'], 'ready')
        self.assertEqual(session['start_payload']['url'], 'http://example.com/#/')
        self.assertEqual(session['start_payload']['navigation_error'], 'timeout')
