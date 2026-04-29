import argparse
import json
import os
import platform
import socket
import sys
import time
import uuid
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


DEFAULT_STATE_FILE = Path.home() / '.testhub_ui_runner.json'


class ApiClient:
    def __init__(self, base_url, username, password, timeout=30):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None

    def login(self):
        response = self.session.post(
            f'{self.base_url}/api/auth/login/',
            json={'username': self.username, 'password': self.password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        self.access_token = data['access']
        self.refresh_token = data['refresh']
        self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})

    def refresh_access_token(self):
        if not self.refresh_token:
            self.login()
            return

        response = self.session.post(
            f'{self.base_url}/api/auth/token/refresh/',
            json={'refresh': self.refresh_token},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            self.login()
            return

        data = response.json()
        self.access_token = data['access']
        if data.get('refresh'):
            self.refresh_token = data['refresh']
        self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})

    def request(self, method, path, **kwargs):
        url = f'{self.base_url}{path}'
        kwargs.setdefault('timeout', self.timeout)
        response = self.session.request(method, url, **kwargs)
        if response.status_code == 401:
            self.refresh_access_token()
            response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()


def load_runner_state(state_file):
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_runner_state(state_file, data):
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def ensure_runner_uuid(state_file):
    state = load_runner_state(state_file)
    runner_uuid = state.get('runner_uuid')
    if not runner_uuid:
        runner_uuid = uuid.uuid4().hex
        state['runner_uuid'] = runner_uuid
        save_runner_state(state_file, state)
    return runner_uuid


def ensure_django():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    import django
    django.setup()


def build_metadata():
    return {
        'python': sys.version.split()[0],
        'platform_version': platform.version(),
        'machine': platform.machine(),
    }


def _normalize_picker_browser(browser):
    return {
        'chrome': 'chromium',
        'edge': 'chromium',
        'firefox': 'firefox',
        'safari': 'webkit',
        'chromium': 'chromium',
        'webkit': 'webkit',
    }.get(str(browser or 'chrome').lower(), 'chromium')


class LocalScrollCoordinatePicker:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.pages = []
        self.active_page = None
        self.session_id = ''
        self.picker_element_data = None
        self.pending_click = None
        self.binding_name = ''
        self.click_setup_script = ''
        self.page_meta = {}
        self.hooked_page_ids = set()

    def _close_runtime(self):
        for item in [self.context, self.browser]:
            if item is None:
                continue
            try:
                item.close()
            except Exception:
                pass

        if self.playwright is not None:
            try:
                self.playwright.stop()
            except Exception:
                pass

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.pages = []
        self.active_page = None
        self.session_id = ''
        self.picker_element_data = None
        self.pending_click = None
        self.binding_name = ''
        self.click_setup_script = ''
        self.page_meta = {}
        self.hooked_page_ids = set()

    def _get_locator(self, element_data, page=None):
        target_page = page or self._get_active_page()
        if not element_data or target_page is None:
            return None

        locator_strategy = str(element_data.get('locator_strategy') or 'css').lower()
        locator_value = str(element_data.get('locator_value') or '')
        if not locator_value:
            return None

        if locator_strategy == 'id':
            return target_page.locator(f'#{locator_value}')
        if locator_strategy in ['css', 'css selector']:
            return target_page.locator(locator_value)
        if locator_strategy == 'xpath':
            return target_page.locator(f'xpath={locator_value}')
        if locator_strategy == 'text':
            return target_page.get_by_text(locator_value)
        if locator_strategy == 'name':
            return target_page.locator(f'[name="{locator_value}"]')
        if locator_strategy == 'placeholder':
            return target_page.get_by_placeholder(locator_value)
        if locator_strategy == 'role':
            return target_page.get_by_role(locator_value)
        if locator_strategy == 'label':
            return target_page.get_by_label(locator_value)
        if locator_strategy == 'title':
            return target_page.get_by_title(locator_value)
        if locator_strategy == 'test-id':
            return target_page.get_by_test_id(locator_value)
        return target_page.locator(locator_value)

    def _build_click_setup_script(self):
        binding_name_json = json.dumps(self.binding_name)
        return f"""
            (() => {{
                const bindingName = {binding_name_json}
                if (window.__testhubScrollCoordinatePickerBindingName === bindingName) {{
                    return
                }}
                window.__testhubScrollCoordinatePickerBindingName = bindingName

                const reportClick = (event) => {{
                    const reporter = window[bindingName]
                    if (typeof reporter !== 'function') {{
                        return
                    }}
                    const x = Math.round(event.clientX || 0)
                    const y = Math.round(event.clientY || 0)
                    const key = `${{Math.round(event.timeStamp || 0)}}:${{x}}:${{y}}:${{event.button}}`
                    if (window.__testhubScrollCoordinatePickerLastKey === key) {{
                        return
                    }}
                    window.__testhubScrollCoordinatePickerLastKey = key
                    reporter({{
                        kind: 'click',
                        x,
                        y,
                        pageX: Math.round(event.pageX || 0),
                        pageY: Math.round(event.pageY || 0),
                        url: window.location.href || '',
                        title: document.title || '',
                    }})
                }}

                document.addEventListener('mousedown', (event) => {{
                    if (event.button !== 2) {{
                        return
                    }}
                    reportClick(event)
                }}, true)

                document.addEventListener('contextmenu', (event) => {{
                    event.preventDefault()
                    reportClick(event)
                }}, true)
            }})()
        """

    def _handle_click(self, source, payload):
        if not isinstance(payload, dict) or payload.get('kind') != 'click':
            return

        pending_click = self.pending_click
        if not pending_click or pending_click.get('payload') is not None:
            return

        source_page = source.get('page') if isinstance(source, dict) else None
        if source_page is not None:
            if source_page not in self.pages:
                self.pages.append(source_page)
            self.active_page = source_page
            self.page_meta[id(source_page)] = {
                'title': str(payload.get('title') or ''),
                'url': str(payload.get('url') or ''),
            }

        pending_click['payload'] = {
            'x': int(payload.get('x') or 0),
            'y': int(payload.get('y') or 0),
            'pageX': int(payload.get('pageX') or 0),
            'pageY': int(payload.get('pageY') or 0),
            'scope': 'click',
            'field': pending_click.get('field') or 'start',
            'url': str(payload.get('url') or ''),
            'title': str(payload.get('title') or ''),
        }
        active_index = 0
        for index, page in enumerate(self.pages):
            if page == source_page:
                active_index = index
                break
        pending_click['payload']['active_page_index'] = active_index

    def _install_click_listener(self, page):
        if page is None or not self.click_setup_script:
            return

        try:
            page.evaluate(self.click_setup_script)
        except Exception:
            pass

        try:
            for frame in page.frames:
                if frame == getattr(page, 'main_frame', None):
                    continue
                try:
                    frame.evaluate(self.click_setup_script)
                except Exception:
                    continue
        except Exception:
            pass

    def _ensure_page_hooks(self, page):
        if page is None:
            return

        page_id = id(page)
        if page_id in self.hooked_page_ids:
            return

        try:
            page.on('domcontentloaded', lambda: self._install_click_listener(page))
        except Exception:
            pass

        try:
            page.on('frameattached', lambda frame: self._install_click_listener(page))
        except Exception:
            pass

        try:
            page.on('framenavigated', lambda frame: self._install_click_listener(page))
        except Exception:
            pass

        self.hooked_page_ids.add(page_id)

    def _register_page(self, page):
        if page is None:
            return

        if page not in self.pages:
            self.pages.append(page)
        self.active_page = page
        self.page_meta[id(page)] = {
            'title': str(self.page_meta.get(id(page), {}).get('title') or ''),
            'url': str(getattr(page, 'url', '') or ''),
        }

        self._ensure_page_hooks(page)
        self._install_click_listener(page)

    def _get_active_page(self):
        try:
            if self.active_page is not None and not self.active_page.is_closed():
                return self.active_page
        except Exception:
            pass

        pages = []
        for page in self.pages:
            try:
                if page is not None and not page.is_closed():
                    pages.append(page)
            except Exception:
                continue

        self.pages = pages
        if pages:
            self.active_page = pages[-1]
            return self.active_page

        try:
            if self.page is not None and not self.page.is_closed():
                return self.page
        except Exception:
            pass
        return None

    def _build_pages_payload(self):
        pages_payload = []
        active_page = self._get_active_page()
        active_index = 0

        for index, page in enumerate(self.pages):
            try:
                if page is None or page.is_closed():
                    continue
            except Exception:
                continue

            page_meta = self.page_meta.get(id(page), {})
            title = str(page_meta.get('title') or '')
            url = str(page_meta.get('url') or getattr(page, 'url', '') or '')

            if page == active_page:
                active_index = len(pages_payload)

            pages_payload.append({
                'index': len(pages_payload),
                'title': title,
                'url': url,
                'is_active': page == active_page,
            })

        return {
            'pages': pages_payload,
            'active_page_index': active_index if pages_payload else 0,
        }

    def _build_open_response(self):
        page = self._get_active_page()
        title = ''
        url = ''
        if page is not None:
            page_meta = self.page_meta.get(id(page), {})
            title = str(page_meta.get('title') or '')
            url = str(page_meta.get('url') or getattr(page, 'url', '') or '')

        return {
            'success': True,
            'session_id': self.session_id,
            'url': url,
            'title': title,
        }

    def list_pages(self):
        if self._get_active_page() is None:
            raise RuntimeError('坐标采集浏览器未启动，请先点击“打开网页”')
        return self._build_pages_payload()

    def select_page(self, page_index):
        pages_payload = self._build_pages_payload().get('pages', [])
        if not pages_payload:
            raise RuntimeError('当前没有可用的采集页面，请先点击“打开网页”')

        try:
            normalized_index = int(page_index)
        except (TypeError, ValueError):
            raise RuntimeError('页面下标无效，请重新选择')

        if normalized_index < 0 or normalized_index >= len(pages_payload):
            raise RuntimeError(f'页面下标超出范围，当前可选范围为 0 ~ {len(pages_payload) - 1}')

        target_page = None
        visible_index = 0
        for page in self.pages:
            try:
                if page is None or page.is_closed():
                    continue
            except Exception:
                continue
            if visible_index == normalized_index:
                target_page = page
                break
            visible_index += 1

        if target_page is None:
            raise RuntimeError('未找到对应的采集页面，请刷新页面列表后重试')

        self.active_page = target_page
        try:
            target_page.bring_to_front()
        except Exception:
            pass
        return self._build_pages_payload()

    def start(self, session_id, base_url, browser='chrome', picker_element_data=None):
        if self.session_id and self.session_id != session_id:
            self._close_runtime()
        elif self.context is not None and self.session_id == session_id:
            self.picker_element_data = picker_element_data or None
            page = self._get_active_page()
            try:
                if page is not None:
                    page.bring_to_front()
            except Exception:
                pass
            return self._build_open_response()

        browser_name = _normalize_picker_browser(browser)
        self._close_runtime()

        self.playwright = sync_playwright().start()
        launcher = getattr(self.playwright, browser_name, self.playwright.chromium)

        launch_args = []
        if browser_name == 'chromium':
            launch_args = [
                '--disable-blink-features=AutomationControlled',
                '--ignore-certificate-errors',
                '--allow-insecure-localhost',
                '--disable-web-security',
                '--disable-translate',
                '--disable-features=Translate,TranslateUI',
                '--lang=zh-CN',
                '--start-maximized',
            ]

        self.browser = launcher.launch(headless=False, args=launch_args)

        context_options = {
            'locale': 'zh-CN',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        }
        if browser_name == 'chromium':
            context_options['no_viewport'] = True
            context_options['extra_http_headers'] = {
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
            }
        else:
            context_options['viewport'] = {'width': 1440, 'height': 900}

        self.context = self.browser.new_context(**context_options)
        self.binding_name = f'__testhubScrollCoordinatePickerReportClick_{session_id[:8]}'
        self.click_setup_script = self._build_click_setup_script()
        self.context.expose_binding(self.binding_name, self._handle_click)
        self.context.add_init_script(self.click_setup_script)
        self.context.on('page', self._register_page)
        self.page = self.context.new_page()
        self._register_page(self.page)
        self.page.goto(base_url, wait_until='domcontentloaded', timeout=30000)
        try:
            self.page.bring_to_front()
        except Exception:
            pass

        self.session_id = session_id
        self.picker_element_data = picker_element_data or None
        self.active_page = self.page
        return self._build_open_response()

    def read_position(self):
        active_page = self._get_active_page()
        if active_page is None:
            raise RuntimeError('坐标采集浏览器未启动，请先重新打开采集窗口')

        if self.picker_element_data:
            locator = self._get_locator(self.picker_element_data, active_page)
            if locator is None:
                raise RuntimeError('滚动元素定位信息无效，请重新选择元素')

            target = locator.first
            target.wait_for(state='attached', timeout=5000)
            payload = target.evaluate("""
                function (element) {
                    const overflowKeywordRe = /(auto|scroll|overlay)/i
                    const scrollKeywordRe = /(scroll|virtual|viewport|wrap|list|container)/i

                    const buildNodeLabel = (node) => {
                        if (!node || !(node instanceof Element)) {
                            return ''
                        }
                        const tag = String(node.tagName || '').toLowerCase()
                        const id = node.id ? `#${node.id}` : ''
                        const classNames = String(node.className || '')
                            .trim()
                            .split(/\\s+/)
                            .filter(Boolean)
                            .slice(0, 4)
                            .map((item) => `.${item}`)
                            .join('')
                        return `${tag}${id}${classNames}`
                    }

                    const getMetrics = (node) => {
                        if (!node) {
                            return {
                                scrollTop: 0,
                                scrollLeft: 0,
                                scrollHeight: 0,
                                clientHeight: 0,
                                scrollWidth: 0,
                                clientWidth: 0,
                                rangeY: 0,
                                rangeX: 0,
                                overflowY: '',
                                overflowX: '',
                                className: '',
                                label: '',
                                hasOverflowStyle: false,
                                hasKeyword: false,
                                hasScrollableRange: false,
                                isActive: false,
                            }
                        }

                        const style = node instanceof Element ? window.getComputedStyle(node) : null
                        const overflowY = style ? (style.overflowY || style.overflow || '') : ''
                        const overflowX = style ? (style.overflowX || style.overflow || '') : ''
                        const scrollTop = Number(node.scrollTop || 0)
                        const scrollLeft = Number(node.scrollLeft || 0)
                        const scrollHeight = Number(node.scrollHeight || 0)
                        const clientHeight = Number(node.clientHeight || 0)
                        const scrollWidth = Number(node.scrollWidth || 0)
                        const clientWidth = Number(node.clientWidth || 0)
                        const rangeY = Math.max(0, scrollHeight - clientHeight)
                        const rangeX = Math.max(0, scrollWidth - clientWidth)
                        const className = String(node.className || '')
                        const id = String(node.id || '')
                        const role = node instanceof Element ? String(node.getAttribute('role') || '') : ''
                        const ariaLabel = node instanceof Element ? String(node.getAttribute('aria-label') || node.getAttribute('title') || '') : ''
                        const hasOverflowStyle = overflowKeywordRe.test(overflowY) || overflowKeywordRe.test(overflowX)
                        const hasKeyword = scrollKeywordRe.test(className) || scrollKeywordRe.test(id) || scrollKeywordRe.test(role) || scrollKeywordRe.test(ariaLabel)
                        const hasScrollableRange = rangeY > 1 || rangeX > 1
                        const isActive = hasScrollableRange || Math.abs(scrollTop) > 0 || Math.abs(scrollLeft) > 0

                        return {
                            scrollTop,
                            scrollLeft,
                            scrollHeight,
                            clientHeight,
                            scrollWidth,
                            clientWidth,
                            rangeY,
                            rangeX,
                            overflowY,
                            overflowX,
                            className,
                            label: buildNodeLabel(node),
                            hasOverflowStyle,
                            hasKeyword,
                            hasScrollableRange,
                            isActive,
                        }
                    }

                    const isDocumentLikeNode = (node) => {
                        if (!node) {
                            return false
                        }
                        return node === document.body || node === document.documentElement || node === document.scrollingElement
                    }

                    const scoreCandidate = (candidate) => {
                        const metrics = candidate.metrics
                        let score = 0
                        score += Math.min(metrics.rangeY, 5000) * 3
                        score += Math.min(metrics.rangeX, 5000) * 3
                        if (Math.abs(metrics.scrollTop) > 0 || Math.abs(metrics.scrollLeft) > 0) {
                            score += 2000
                        }
                        if (metrics.hasOverflowStyle) {
                            score += 400
                        }
                        if (metrics.hasKeyword) {
                            score += 250
                        }
                        if (candidate.source === 'self') {
                            score += 150
                        } else if (candidate.source === 'descendant') {
                            score += 300
                        } else if (candidate.source === 'ancestor') {
                            score += 100
                        }
                        return score
                    }

                    const createCandidate = (node, source) => {
                        const metrics = getMetrics(node)
                        return {
                            node,
                            source,
                            metrics,
                            score: scoreCandidate({ node, source, metrics }),
                        }
                    }

                    const pickBestCandidate = (root) => {
                        const subtreeCandidates = [createCandidate(root, 'self')]
                        const descendants = root.querySelectorAll('*')
                        for (const item of descendants) {
                            subtreeCandidates.push(createCandidate(item, 'descendant'))
                        }
                        const activeSubtree = subtreeCandidates
                            .filter((candidate) => candidate.metrics.isActive)
                            .sort((left, right) => right.score - left.score)
                        if (activeSubtree.length) {
                            return activeSubtree[0]
                        }

                        const ancestorCandidates = []
                        let parent = root.parentElement
                        while (parent) {
                            if (!isDocumentLikeNode(parent)) {
                                ancestorCandidates.push(createCandidate(parent, 'ancestor'))
                            }
                            parent = parent.parentElement
                        }
                        const activeAncestors = ancestorCandidates
                            .filter((candidate) => candidate.metrics.isActive)
                            .sort((left, right) => right.score - left.score)
                        if (activeAncestors.length) {
                            return activeAncestors[0]
                        }

                        const fallbackCandidates = subtreeCandidates.concat(ancestorCandidates)
                        return fallbackCandidates.sort((left, right) => right.score - left.score)[0] || createCandidate(root, 'self')
                    }

                    const chosen = pickBestCandidate(element)
                    const scrollTarget = chosen.node || element
                    const metrics = chosen.metrics || getMetrics(scrollTarget)

                    return {
                        x: Math.round(metrics.scrollLeft || 0),
                        y: Math.round(metrics.scrollTop || 0),
                        scope: 'element',
                        elementTag: scrollTarget.tagName || '',
                        elementName: scrollTarget.getAttribute('aria-label') || scrollTarget.getAttribute('title') || '',
                        className: metrics.className || '',
                        scrollHeight: Number(metrics.scrollHeight || 0),
                        clientHeight: Number(metrics.clientHeight || 0),
                        scrollWidth: Number(metrics.scrollWidth || 0),
                        clientWidth: Number(metrics.clientWidth || 0),
                        scrollRangeY: Number(metrics.rangeY || 0),
                        scrollRangeX: Number(metrics.rangeX || 0),
                        overflowY: metrics.overflowY || '',
                        overflowX: metrics.overflowX || '',
                        resolvedTarget: metrics.label || '',
                        candidateSource: chosen.source || 'self',
                        canScroll: Boolean(metrics.hasScrollableRange),
                    }
                }
            """)
            payload['target_name'] = self.picker_element_data.get('name') or ''
            return payload

        return active_page.evaluate("""
            () => ({
                x: Math.round(window.scrollX || 0),
                y: Math.round(window.scrollY || 0),
                scope: 'window',
                url: window.location.href || ''
            })
        """)

    def close(self):
        self._close_runtime()
        return {'success': True}

    def capture_click(self, field='start', timeout=120):
        page = self._get_active_page()
        if page is None:
            raise RuntimeError('坐标采集浏览器未启动，请先点击“打开网页”')

        try:
            page.bring_to_front()
        except Exception:
            pass

        pending_click = {
            'field': str(field or 'start').strip() or 'start',
            'payload': None,
        }
        self.pending_click = pending_click
        deadline = time.time() + max(timeout, 1)

        try:
            while time.time() < deadline:
                if pending_click.get('payload') is not None:
                    return pending_click['payload']

                active_page = self._get_active_page()
                if active_page is not None:
                    try:
                        active_page.wait_for_timeout(100)
                    except Exception:
                        time.sleep(0.1)
                else:
                    time.sleep(0.1)

            raise TimeoutError('未捕捉到鼠标右键，请先点击“打开网页”，然后在打开的网页中右键一次')
        finally:
            if self.pending_click is pending_click:
                self.pending_click = None


def parse_args():
    parser = argparse.ArgumentParser(description='TestHub UI automation local runner')
    parser.add_argument('--server', required=True, help='TestHub server base URL, e.g. http://192.168.1.10:8000')
    parser.add_argument('--username', required=True, help='Login username')
    parser.add_argument('--password', required=True, help='Login password')
    parser.add_argument('--name', default='', help='Runner display name')
    parser.add_argument('--poll-interval', type=float, default=3.0, help='Polling interval in seconds')
    parser.add_argument('--state-file', default=str(DEFAULT_STATE_FILE), help='Runner state file path')
    return parser.parse_args()


def main():
    args = parse_args()
    state_file = Path(args.state_file)
    runner_uuid = ensure_runner_uuid(state_file)

    hostname = socket.gethostname()
    runner_name = args.name or f'{hostname}-ui-runner'
    client = ApiClient(args.server, args.username, args.password)
    client.login()

    ensure_django()
    from apps.ui_automation.local_execution_service import execute_serialized_test_case
    picker = LocalScrollCoordinatePicker()

    register_payload = {
        'runner_uuid': runner_uuid,
        'name': runner_name,
        'hostname': hostname,
        'platform': platform.platform(),
        'metadata': build_metadata(),
    }
    register_result = client.request('POST', '/api/ui-automation/local-runners/register/', json=register_payload)
    print(f"Runner registered: {register_result.get('name', runner_name)} ({runner_uuid})")

    idle_sleep = max(args.poll_interval, 1.0)
    error_sleep = min(max(args.poll_interval, 3.0), 10.0)

    while True:
        try:
            client.request(
                'POST',
                '/api/ui-automation/local-runners/heartbeat/',
                json={'runner_uuid': runner_uuid, 'metadata': build_metadata()},
            )
            claim = client.request(
                'POST',
                '/api/ui-automation/local-runners/claim/',
                json={'runner_uuid': runner_uuid},
            )
            task = claim.get('task')
            if not task:
                time.sleep(idle_sleep)
                continue

            if task.get('task_type') == 'scroll_coordinate_picker':
                session_id = task.get('session_id')
                action = task.get('action')
                command_sequence = task.get('command_sequence')
                print(f"Claimed coordinate picker task: {action} ({session_id})")

                try:
                    if action == 'start':
                        payload = picker.start(
                            session_id,
                            task.get('base_url', ''),
                            task.get('browser', 'chrome'),
                            picker_element_data=task.get('picker_element_data') or None,
                        )
                    elif action == 'read_position':
                        picker.picker_element_data = task.get('picker_element_data') or picker.picker_element_data
                        payload = picker.read_position()
                    elif action == 'capture_click':
                        picker.picker_element_data = task.get('picker_element_data') or picker.picker_element_data
                        payload = picker.capture_click(
                            field=task.get('field') or 'start',
                            timeout=120,
                        )
                    elif action == 'list_pages':
                        payload = picker.list_pages()
                    elif action == 'select_page':
                        payload = picker.select_page(task.get('page_index'))
                    elif action == 'close':
                        payload = picker.close()
                    else:
                        raise RuntimeError(f'Unsupported coordinate picker action: {action}')

                    client.request(
                        'POST',
                        '/api/ui-automation/local-runners/report/',
                        json={
                            'runner_uuid': runner_uuid,
                            'task_type': 'scroll_coordinate_picker',
                            'session_id': session_id,
                            'action': action,
                            'command_sequence': command_sequence,
                            'success': True,
                            'payload': payload,
                        },
                    )
                except Exception as exc:
                    client.request(
                        'POST',
                        '/api/ui-automation/local-runners/report/',
                        json={
                            'runner_uuid': runner_uuid,
                            'task_type': 'scroll_coordinate_picker',
                            'session_id': session_id,
                            'action': action,
                            'command_sequence': command_sequence,
                            'success': False,
                            'error_message': str(exc),
                        },
                    )
                time.sleep(0.3)
                continue

            execution_id = task['execution_id']
            payload = task['payload']
            print(f"Claimed execution #{execution_id}: {payload.get('test_case_name')}")
            result = execute_serialized_test_case(
                payload,
                engine_type=task.get('engine', 'playwright'),
                browser=task.get('browser', 'chrome'),
                headless=task.get('headless', False),
            )
            client.request(
                'POST',
                '/api/ui-automation/local-runners/report/',
                json={
                    'runner_uuid': runner_uuid,
                    'execution_id': execution_id,
                    **result,
                },
            )
            print(f"Reported execution #{execution_id}: {result.get('status')}")
        except KeyboardInterrupt:
            picker.close()
            print('Runner stopped by user')
            break
        except Exception as exc:
            print(f'Runner loop error: {exc}')
            time.sleep(error_sleep)


if __name__ == '__main__':
    main()
