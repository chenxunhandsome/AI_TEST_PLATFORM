import hashlib
import json
import logging
import os
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
from django.db import close_old_connections, models, transaction
from django.utils import timezone
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .locator_strategy_defaults import ensure_default_locator_strategies
from .models import (
    Element,
    ElementGroup,
    LocatorStrategy,
    UIPageEdge,
    UIPageElement,
    UIPageGraph,
    UIPageNode,
    UiProject,
)

logger = logging.getLogger(__name__)

PAGE_GRAPH_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='page-graph-crawl')
PAGE_GRAPH_STALE_RUNNING_MINUTES = 30
PAGE_GRAPH_PROCESS_STARTED_AT = timezone.now()
PAGE_GRAPH_RESTART_GRACE_SECONDS = 10
PAGE_GRAPH_LOGIN_HEARTBEAT_SECONDS = 5
PAGE_GRAPH_LOGIN_STALE_SECONDS = 120
PAGE_GRAPH_LOGIN_MAX_TIMEOUT_SECONDS = 180

INTERACTIVE_SELECTOR = (
    'a[href], button, input, textarea, select, [role="button"], [role="link"], '
    '[role="menuitem"], [role="tab"], [role="option"], [onclick], [data-testid], '
    '[data-test], [aria-label]'
)

DANGEROUS_TEXT_RE = re.compile(
    r'(删除|移除|注销|退出|登出|清空|重置|提交|保存|确定|确认|禁用|启用|delete|remove|logout|submit|save|confirm|reset)',
    re.I,
)
NAVIGATION_TEXT_RE = re.compile(
    r'(首页|主页|管理|列表|中心|设置|配置|查询|搜索|报表|统计|页面|菜单|详情|工作台|dashboard|home|list|manage|setting|config|report|search)',
    re.I,
)

DYNAMIC_TOKEN_RE = re.compile(
    r'(^\d+$|[0-9]{6,}|[a-f0-9]{8,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|'
    r'\b\d{10,13}\b|^[A-Za-z0-9_-]{12,}$)',
    re.I,
)
VOLATILE_CLASS_RE = re.compile(r'(active|selected|disabled|hover|focus|open|show|hide|enter|leave|transition|loading)', re.I)
STRUCTURAL_LOCATOR_RE = re.compile(r'(:nth-of-type\(|/\w+\[\d+\]|^\s*//(?:\w+\[\d+\]/?)+\s*$)', re.I)

DANGEROUS_TEXT_RE = re.compile(
    r'(删除|移除|注销|退出|登出|清空|重置|提交|保存|确定|确认|禁用|启用|delete|remove|logout|submit|save|confirm|reset)',
    re.I,
)


@dataclass
class CrawlOptions:
    start_url: str
    login_url: str = ''
    extra_start_urls: tuple = ()
    username: str = ''
    password: str = ''
    username_selector: str = ''
    password_selector: str = ''
    submit_selector: str = ''
    max_pages: int = 30
    max_depth: int = 3
    max_actions: int = 1000
    max_actions_per_page: int = 80
    timeout_minutes: int = 180
    retry_count: int = 1
    allow_destructive_actions: bool = False
    headless: bool = True
    timeout_ms: int = 15000
    sync_elements: bool = True


class DbThreadRunner:
    """Run Django ORM work outside Playwright's sync API event-loop thread."""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='page-graph-db')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.executor.shutdown(wait=True)

    def __call__(self, func, *args, **kwargs):
        def run():
            close_old_connections()
            try:
                return func(*args, **kwargs)
            finally:
                close_old_connections()

        return self.executor.submit(run).result()


class PageGraphCrawlTimeout(RuntimeError):
    pass


class PageGraphCrawlCancelled(RuntimeError):
    pass


def initial_graph_progress(options, started_at=None):
    return {
        'stage': 'pending',
        'current_url': '',
        'visited_count': 0,
        'queued_count': 0,
        'discovered_state_count': 0,
        'visited_state_count': 0,
        'pending_state_count': 0,
        'coverage_status': 'unknown',
        'coverage_message': '',
        'termination_reason': '',
        'clicked_count': 0,
        'failed_action_count': 0,
        'node_count': 0,
        'edge_count': 0,
        'element_count': 0,
        'synced_element_count': 0,
        'max_pages': options.max_pages,
        'max_depth': options.max_depth,
        'max_actions': options.max_actions,
        'max_actions_per_page': options.max_actions_per_page,
        'timeout_minutes': options.timeout_minutes,
        'started_at': started_at.isoformat() if started_at else '',
        'updated_at': timezone.now().isoformat(),
    }


def update_graph_status(graph_id, **fields):
    close_old_connections()
    fields['updated_at'] = timezone.now()
    try:
        UIPageGraph.objects.filter(id=graph_id).update(**fields)
    except Exception:
        close_old_connections()
        UIPageGraph.objects.filter(id=graph_id).update(**fields)
    finally:
        close_old_connections()


def update_graph_progress(graph_id, **progress_updates):
    close_old_connections()
    graph = UIPageGraph.objects.filter(id=graph_id).only('progress', 'crawl_state').first()
    if not graph:
        return
    progress = dict(graph.progress or {})
    progress.update(progress_updates)
    progress['updated_at'] = timezone.now().isoformat()
    update_graph_status(graph_id, progress=progress, heartbeat_at=timezone.now())


def update_graph_crawl_state(graph_id, **state_updates):
    close_old_connections()
    graph = UIPageGraph.objects.filter(id=graph_id).only('crawl_state').first()
    if not graph:
        return
    state = dict(graph.crawl_state or {})
    state.update(state_updates)
    state['updated_at'] = timezone.now().isoformat()
    update_graph_status(graph_id, crawl_state=state, heartbeat_at=timezone.now())


def final_graph_progress(graph_id, options, status, summary=None, error_message=''):
    close_old_connections()
    graph = UIPageGraph.objects.filter(id=graph_id).only('progress', 'crawl_state').first()
    progress = dict((graph.progress if graph else {}) or initial_graph_progress(options))
    progress.update({
        'stage': status,
        'status': status,
        'error_message': error_message,
        'updated_at': timezone.now().isoformat(),
    })
    coverage = dict((summary or {}).get('coverage') or {})
    if not coverage:
        coverage = build_coverage_from_state(
            progress,
            graph.crawl_state if graph else {},
            options,
            status=status,
            error_message=error_message,
        )
    if summary:
        progress.update({
            'node_count': summary.get('pages', progress.get('node_count', 0)),
            'edge_count': summary.get('edges', progress.get('edge_count', 0)),
            'element_count': summary.get('elements', progress.get('element_count', 0)),
            'synced_element_count': summary.get('synced_elements', progress.get('synced_element_count', 0)),
        })
    progress.update(coverage)
    return progress


def build_coverage_snapshot(discovered, visited, pending, clicked_count, failed_action_count, options, status='running', error_message=''):
    discovered_count = len(discovered or [])
    visited_count = len(visited or [])
    pending_count = len(pending or [])
    max_pages_reached = visited_count >= options.max_pages or discovered_count >= options.max_pages
    max_actions_reached = clicked_count >= options.max_actions
    if status == 'completed':
        if pending_count <= 0 and not max_pages_reached and not max_actions_reached:
            coverage_status = 'complete'
            termination_reason = 'queue_empty'
            coverage_message = '待展开队列已清空，未触达页面数或操作数上限'
        elif max_pages_reached:
            coverage_status = 'limited'
            termination_reason = 'max_pages_reached'
            coverage_message = f'已达到最大页面节点数 {options.max_pages}，可能仍有页面未爬取'
        elif max_actions_reached:
            coverage_status = 'limited'
            termination_reason = 'max_actions_reached'
            coverage_message = f'已达到最大操作数 {options.max_actions}，可能仍有操作路径未展开'
        elif pending_count > 0:
            coverage_status = 'incomplete'
            termination_reason = 'pending_states_remaining'
            coverage_message = f'仍有 {pending_count} 个已发现状态未展开，建议继续爬取'
        else:
            coverage_status = 'complete'
            termination_reason = 'queue_empty'
            coverage_message = '待展开队列已清空'
    elif status == 'timeout':
        coverage_status = 'incomplete'
        termination_reason = 'timeout'
        coverage_message = error_message or '爬取超时，仍可能有页面未展开'
    elif status == 'cancelled':
        coverage_status = 'incomplete'
        termination_reason = 'cancelled'
        coverage_message = error_message or '爬取已取消，仍可能有页面未展开'
    elif status == 'failed':
        coverage_status = 'failed'
        termination_reason = 'failed'
        coverage_message = error_message or '爬取失败'
    elif status == 'running':
        coverage_status = 'running'
        termination_reason = ''
        coverage_message = f'正在爬取，待展开 {pending_count} 个状态'
    else:
        coverage_status = 'unknown'
        termination_reason = ''
        coverage_message = ''

    return {
        'coverage_status': coverage_status,
        'coverage_message': coverage_message,
        'termination_reason': termination_reason,
        'discovered_state_count': discovered_count,
        'visited_state_count': visited_count,
        'pending_state_count': pending_count,
        'queued_count': pending_count,
        'visited_count': visited_count,
        'max_pages_reached': max_pages_reached,
        'max_actions_reached': max_actions_reached,
    }


def build_coverage_from_state(progress, crawl_state, options, status='running', error_message=''):
    state = crawl_state or {}
    discovered = set(state.get('discovered') or state.get('queued') or [])
    visited = set(state.get('visited') or [])
    pending = set(state.get('pending') or [])
    if not pending and discovered:
        pending = discovered - visited
    progress_pending = int((progress or {}).get('pending_state_count') or (progress or {}).get('queued_count') or 0)
    if progress_pending > len(pending):
        pending.update(f'__pending__{index}' for index in range(progress_pending - len(pending)))
    if len(discovered) < len(visited) + len(pending):
        discovered.update(visited)
        discovered.update(pending)
    clicked_count = int((progress or {}).get('clicked_count') or len(state.get('clicked_actions') or []))
    failed_action_count = int((progress or {}).get('failed_action_count') or 0)
    return build_coverage_snapshot(
        discovered,
        visited,
        pending,
        clicked_count,
        failed_action_count,
        options,
        status=status,
        error_message=error_message,
    )


def ensure_graph_not_timed_out(started_at, options):
    if started_at and timezone.now() - started_at > timedelta(minutes=options.timeout_minutes):
        raise PageGraphCrawlTimeout(f'页面图谱爬取超过最大运行时长 {options.timeout_minutes} 分钟，已自动终止')


def login_timeout_seconds_for_options(options):
    timeout_ms = int(getattr(options, 'timeout_ms', 15000) or 15000)
    timeout_seconds = max(60, int(timeout_ms / 1000) * 6)
    return min(timeout_seconds, PAGE_GRAPH_LOGIN_MAX_TIMEOUT_SECONDS)


def ensure_graph_not_cancelled(graph_id):
    close_old_connections()
    status = UIPageGraph.objects.filter(id=graph_id).values_list('status', flat=True).first()
    if status == 'cancelled':
        raise PageGraphCrawlCancelled('页面图谱爬取已取消')


def mark_stale_page_graphs(timeout_minutes=PAGE_GRAPH_STALE_RUNNING_MINUTES):
    threshold = timezone.now() - timedelta(minutes=timeout_minutes)
    process_start_threshold = PAGE_GRAPH_PROCESS_STARTED_AT - timedelta(seconds=PAGE_GRAPH_RESTART_GRACE_SECONDS)
    stale_graphs = list(
        UIPageGraph.objects.filter(
            status__in=['pending', 'running'],
        ).filter(
            models.Q(heartbeat_at__lt=threshold) |
            models.Q(heartbeat_at__isnull=True, started_at__lt=threshold) |
            models.Q(heartbeat_at__isnull=True, started_at__isnull=True, created_at__lt=threshold) |
            models.Q(heartbeat_at__lt=process_start_threshold) |
            models.Q(heartbeat_at__isnull=True, started_at__lt=process_start_threshold) |
            models.Q(heartbeat_at__isnull=True, started_at__isnull=True, created_at__lt=process_start_threshold)
        )
    )
    stale_by_id = {graph.id: (graph, 'stale') for graph in stale_graphs}
    login_threshold = timezone.now() - timedelta(seconds=PAGE_GRAPH_LOGIN_STALE_SECONDS)
    login_stale_graphs = UIPageGraph.objects.filter(
        status='running',
        heartbeat_at__lt=login_threshold,
    )
    for graph in login_stale_graphs:
        if str((graph.progress or {}).get('stage') or '') == 'login':
            stale_by_id.setdefault(graph.id, (graph, 'login_stalled'))
    now = timezone.now()
    for graph, stale_reason in stale_by_id.values():
        restarted_before_graph_finished = (
            (graph.heartbeat_at and graph.heartbeat_at < process_start_threshold)
            or (not graph.heartbeat_at and graph.started_at and graph.started_at < process_start_threshold)
            or (not graph.heartbeat_at and not graph.started_at and graph.created_at < process_start_threshold)
        )
        message = f'页面图谱爬取心跳超过 {timeout_minutes} 分钟未更新，已自动标记为超时'
        if stale_reason == 'login_stalled':
            message = '页面图谱爬取卡在登录阶段，心跳超过 2 分钟未更新，已自动标记为超时，可点击“继续”重试'
        elif restarted_before_graph_finished:
            message = '页面图谱爬取任务在后端重启后已中断，已自动标记为超时，可点击“继续”恢复爬取'
        else:
            message = f'页面图谱爬取心跳超过 {timeout_minutes} 分钟未更新，已自动标记为超时，可点击“继续”恢复爬取'
        progress = dict(graph.progress or {})
        options = SimpleNamespace(
            max_pages=int((graph.crawl_config or {}).get('max_pages') or progress.get('max_pages') or 30),
            max_actions=int((graph.crawl_config or {}).get('max_actions') or progress.get('max_actions') or 1000),
        )
        coverage = build_coverage_from_state(
            progress,
            graph.crawl_state or {},
            options,
            status='timeout',
            error_message=message,
        )
        progress.update({'stage': 'timeout', 'status': 'timeout', 'error_message': message, 'updated_at': now.isoformat(), **coverage})
        crawl_state = dict(graph.crawl_state or {})
        crawl_state['coverage'] = coverage
        crawl_state['updated_at'] = now.isoformat()
        UIPageGraph.objects.filter(id=graph.id).update(
            status='timeout',
            error_message=message,
            completed_at=now,
            heartbeat_at=now,
            progress=progress,
            crawl_state=crawl_state,
            updated_at=now,
        )
    return len(stale_by_id)


def normalize_url(url):
    cleaned = str(url or '').strip()
    if not cleaned:
        return ''
    parsed = urlparse(cleaned)
    suffix = f'#{parsed.fragment}' if parsed.fragment else ''
    path_part = cleaned[:-len(suffix)] if suffix else cleaned
    if suffix and parsed.path in {'', '/'} and not parsed.query:
        base = f'{parsed.scheme}://{parsed.netloc}/' if parsed.scheme and parsed.netloc else path_part
        return base + suffix
    return path_part.rstrip('/') + suffix if path_part.rstrip('/') else cleaned


def route_key_for_url(url):
    parsed = urlparse(normalize_url(url))
    path = parsed.path or '/'
    query = f'?{parsed.query}' if parsed.query else ''
    fragment = f'#{parsed.fragment}' if parsed.fragment else ''
    if fragment and path != '/' and not path.endswith('/'):
        path = f'{path}/'
    return f'{path}{query}{fragment}'[:500]


def same_origin(url, base_url):
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    return (
        parsed_url.scheme in {'http', 'https'}
        and parsed_base.scheme in {'http', 'https'}
        and parsed_url.netloc == parsed_base.netloc
    )


def compact_text(value, limit=500):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    return text[:limit]


def normalize_keyword_text(value):
    return re.sub(r'[\s_\-（）()【】\[\]:：,，.。/\\]+', '', str(value or '').strip().lower())


def extract_keywords(*values, limit=20):
    keywords = []
    for value in values:
        text = str(value or '')
        for token in re.findall(r'[\u4e00-\u9fff]{2,12}|[A-Za-z][A-Za-z0-9_\-]{1,40}', text):
            token = token.strip()
            normalized = normalize_keyword_text(token)
            if normalized and normalized not in {normalize_keyword_text(item) for item in keywords}:
                keywords.append(token[:40])
            if len(keywords) >= limit:
                return keywords
    return keywords


def infer_element_type(tag, input_type, role, text):
    tag = str(tag or '').lower()
    input_type = str(input_type or '').lower()
    role = str(role or '').lower()
    if tag == 'input':
        if input_type in {'checkbox'}:
            return 'CHECKBOX'
        if input_type in {'radio'}:
            return 'RADIO'
        return 'INPUT'
    if tag == 'textarea':
        return 'INPUT'
    if tag == 'select' or role in {'combobox', 'listbox', 'option'}:
        return 'DROPDOWN'
    if tag == 'a' or role == 'link':
        return 'LINK'
    if tag == 'button' or role in {'button', 'menuitem', 'tab'}:
        return 'BUTTON'
    if tag == 'img':
        return 'IMAGE'
    if '表' in str(text or '') or tag == 'table':
        return 'TABLE'
    return 'CONTAINER'


def locator_name_for_strategy(strategy):
    names = {
        'css': ['css', 'CSS', 'Css'],
        'xpath': ['XPath', 'xpath', 'XPATH'],
        'text': ['text', 'Text', 'TEXT'],
    }
    return names.get(str(strategy or '').lower(), [strategy])[0]


def get_locator_strategy(strategy):
    ensure_default_locator_strategies()
    candidates = {
        'css': ['css', 'CSS', 'Css'],
        'xpath': ['XPath', 'xpath', 'XPATH'],
        'text': ['text', 'Text', 'TEXT'],
    }.get(str(strategy or '').lower(), [strategy])
    found = LocatorStrategy.objects.filter(name__in=candidates).first()
    if found:
        return found
    return LocatorStrategy.objects.create(name=locator_name_for_strategy(strategy), description='Generated by page graph crawler')


def score_locator(locator):
    strategy = str(locator.get('strategy') or '').lower()
    value = str(locator.get('value') or '')
    if not value or not is_stable_locator_value(value):
        return 0
    if strategy == 'test-id' or '[data-testid=' in value or '[data-test=' in value or '[data-cy=' in value:
        return 100
    if strategy in {'name', 'id'}:
        return 92
    if strategy == 'id' or value.startswith('#'):
        return 90
    if strategy in {'placeholder', 'title'}:
        return 84
    if 'aria-label' in value or 'placeholder' in value or 'title=' in value:
        return 78
    if strategy == 'text':
        return 70
    if strategy == 'xpath' and 'normalize-space' in value:
        return 65
    if strategy == 'css':
        return 55
    return 40


def choose_best_locator(page, locators):
    checked = []
    for locator in sorted(locators, key=score_locator, reverse=True):
        strategy = locator.get('strategy')
        value = locator.get('value')
        if not value or not is_stable_locator_value(value):
            continue
        try:
            strategy_name = str(strategy or '').lower()
            if strategy_name == 'xpath':
                count = page.locator(f'xpath={value}').count()
            elif strategy_name == 'text':
                count = page.get_by_text(value, exact=True).count()
            elif strategy_name == 'id':
                count = page.locator(f'#{css_escape(value)}').count()
            elif strategy_name == 'name':
                count = page.locator(f'[name="{css_escape(value)}"]').count()
            elif strategy_name == 'placeholder':
                count = page.get_by_placeholder(value, exact=True).count()
            elif strategy_name == 'title':
                count = page.get_by_title(value).count()
            elif strategy_name == 'test-id':
                count = page.get_by_test_id(value).count()
            else:
                count = page.locator(value).count()
        except Exception:
            count = 0
        item = dict(locator)
        item['match_count'] = count
        item['is_unique'] = count == 1
        checked.append(item)
        if count == 1:
            return item, checked
    return (checked[0] if checked else {'strategy': 'xpath', 'value': '//*', 'match_count': 0, 'is_unique': False}), checked


def css_escape(value):
    return str(value or '').replace('\\', '\\\\').replace('"', '\\"')


def xpath_literal(value):
    text = str(value or '')
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in text.split("'")) + ")"


def is_dynamic_token(value):
    text = str(value or '').strip()
    if not text:
        return True
    if re.search(r'(^|[-_])(id[-_]?)?\d+([_-]\d+)+$', text, re.I):
        return True
    if re.search(r'^el-id-\d+-\d+$', text, re.I):
        return True
    normalized = re.sub(r'[^A-Za-z0-9_-]+', '', text)
    if DYNAMIC_TOKEN_RE.search(text) or DYNAMIC_TOKEN_RE.search(normalized):
        return True
    if len(normalized) >= 12:
        has_alpha = bool(re.search(r'[A-Za-z]', normalized))
        has_digit = bool(re.search(r'\d', normalized))
        has_semantic_word = bool(re.search(
            r'(test|qa|button|btn|input|menu|nav|user|name|password|login|search|submit|link|table|form)',
            normalized,
            re.I,
        ))
        if has_alpha and has_digit and not has_semantic_word:
            return True
    return False


def is_stable_attribute_value(value):
    return bool(str(value or '').strip()) and not is_dynamic_token(value)


def is_stable_locator_value(value):
    text = str(value or '').strip()
    if not text:
        return False
    if STRUCTURAL_LOCATOR_RE.search(text):
        return False
    quoted_values = re.findall(r'["\']([^"\']+)["\']', text)
    return not any(is_dynamic_token(item) for item in quoted_values)


def add_candidate(candidates, strategy, value):
    if is_stable_locator_value(value):
        candidates.append({'strategy': strategy, 'value': str(value).strip()})


def build_locator_candidates(item):
    tag = item.get('tag') or '*'
    text = compact_text(item.get('text'), 80)
    attrs = item.get('attributes') or {}
    candidates = []

    test_id = attrs.get('data-testid')
    if is_stable_attribute_value(test_id):
        add_candidate(candidates, 'test-id', test_id)

    for attr in ('data-test', 'data-cy', 'data-qa'):
        value = attrs.get(attr)
        if is_stable_attribute_value(value):
            add_candidate(candidates, 'CSS', f'{tag}[{attr}="{css_escape(value)}"]')

    name_value = attrs.get('name')
    if is_stable_attribute_value(name_value):
        add_candidate(candidates, 'name', name_value)
        add_candidate(candidates, 'CSS', f'{tag}[name="{css_escape(name_value)}"]')

    element_id = attrs.get('id')
    if is_stable_attribute_value(element_id):
        add_candidate(candidates, 'ID', element_id)
        add_candidate(candidates, 'CSS', f'#{css_escape(element_id)}')

    aria_label = attrs.get('aria-label')
    if is_stable_attribute_value(aria_label):
        add_candidate(candidates, 'CSS', f'{tag}[aria-label="{css_escape(aria_label)}"]')
        add_candidate(candidates, 'XPath', f'//{tag}[@aria-label={xpath_literal(aria_label)}]')

    placeholder = attrs.get('placeholder')
    if is_stable_attribute_value(placeholder):
        add_candidate(candidates, 'placeholder', placeholder)
        add_candidate(candidates, 'CSS', f'{tag}[placeholder="{css_escape(placeholder)}"]')
        add_candidate(candidates, 'XPath', f'//{tag}[@placeholder={xpath_literal(placeholder)}]')

    title = attrs.get('title')
    if is_stable_attribute_value(title):
        add_candidate(candidates, 'title', title)
        add_candidate(candidates, 'CSS', f'{tag}[title="{css_escape(title)}"]')

    if text and is_stable_attribute_value(text):
        add_candidate(candidates, 'text', text)
        add_candidate(candidates, 'XPath', f'//{tag}[normalize-space(.)={xpath_literal(text)}]')
        add_candidate(candidates, 'XPath', f'//*[normalize-space(.)={xpath_literal(text)}]')

    class_name = attrs.get('class')
    stable_classes = [
        item for item in re.split(r'\s+', str(class_name or '').strip())
        if item and not VOLATILE_CLASS_RE.search(item) and is_stable_attribute_value(item)
    ][:2]
    if stable_classes:
        add_candidate(candidates, 'CSS', f'{tag}.' + '.'.join(css_escape(item) for item in stable_classes))

    dom_path = item.get('css_path')
    if dom_path:
        add_candidate(candidates, 'CSS', dom_path)
    xpath = item.get('xpath')
    if xpath:
        add_candidate(candidates, 'XPath', xpath)

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        key = (candidate.get('strategy'), candidate.get('value'))
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)
    return unique_candidates


def dom_signature(item):
    attrs = item.get('attributes') or {}
    payload = '|'.join([
        item.get('tag') or '',
        item.get('role') or '',
        attrs.get('id') or '',
        attrs.get('name') or '',
        attrs.get('data-testid') or attrs.get('data-test') or attrs.get('data-cy') or '',
        compact_text(item.get('text'), 80),
    ])
    return hashlib.sha1(payload.encode('utf-8', errors='ignore')).hexdigest()


def page_extract_script():
    return r"""
() => {
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  };
  const dynamicToken = (value) => {
    const text = String(value || '').trim();
    if (!text) return true;
    const normalized = text.replace(/[^A-Za-z0-9_-]+/g, '');
    if (/^\d+$|[0-9]{6,}|[a-f0-9]{8,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\b\d{10,13}\b|^[A-Za-z0-9_-]{12,}$/i.test(text)) return true;
    if (/^\d+$|[0-9]{6,}|[a-f0-9]{8,}|^[A-Za-z0-9_-]{12,}$/i.test(normalized)) return true;
    if (normalized.length >= 12 && /[A-Za-z]/.test(normalized) && /\d/.test(normalized) && !/(test|qa|button|btn|input|menu|nav|user|name|password|login|search|submit|link|table|form)/i.test(normalized)) return true;
    return false;
  };
  const stableValue = (value) => Boolean(String(value || '').trim()) && !dynamicToken(value);
  const stableClass = (value) => stableValue(value) && !/(active|selected|disabled|hover|focus|open|show|hide|enter|leave|transition|loading)/i.test(value);
  const attrs = (el) => {
    const keys = ['id','class','name','type','placeholder','aria-label','title','role','href','data-testid','data-test','data-cy','data-qa'];
    const result = {};
    for (const key of keys) {
      const value = el.getAttribute(key);
      if (value) result[key] = value;
    }
    return result;
  };
  const cssPath = (el) => {
    const parts = [];
    let current = el;
    while (current && current.nodeType === 1 && current !== document.body && parts.length < 6) {
      let part = current.tagName.toLowerCase();
      const testId = current.getAttribute('data-testid') || current.getAttribute('data-test') || current.getAttribute('data-cy');
      if (testId) {
        part += `[${current.getAttribute('data-testid') ? 'data-testid' : current.getAttribute('data-test') ? 'data-test' : 'data-cy'}="${CSS.escape(testId)}"]`;
        parts.unshift(part);
        break;
      }
      if (stableValue(current.id)) {
        part += `#${CSS.escape(current.id)}`;
        parts.unshift(part);
        break;
      }
      const name = current.getAttribute('name');
      if (stableValue(name)) {
        part += `[name="${CSS.escape(name)}"]`;
        parts.unshift(part);
        break;
      }
      const stableClasses = Array.from(current.classList || []).filter(stableClass).slice(0, 2);
      if (stableClasses.length) {
        part += stableClasses.map((item) => `.${CSS.escape(item)}`).join('');
        parts.unshift(part);
        break;
      }
      const siblings = Array.from(current.parentElement ? current.parentElement.children : []);
      const sameTag = siblings.filter((node) => node.tagName === current.tagName);
      if (sameTag.length > 1) part += `:nth-of-type(${sameTag.indexOf(current) + 1})`;
      parts.unshift(part);
      current = current.parentElement;
    }
    return parts.join(' > ');
  };
  const xpath = (el) => {
    const parts = [];
    let current = el;
    while (current && current.nodeType === 1 && current !== document.body && parts.length < 6) {
      const tag = current.tagName.toLowerCase();
      const siblings = Array.from(current.parentElement ? current.parentElement.children : []).filter((node) => node.tagName === current.tagName);
      const index = siblings.length > 1 ? `[${siblings.indexOf(current) + 1}]` : '';
      parts.unshift(`${tag}${index}`);
      current = current.parentElement;
    }
    return '//' + parts.join('/');
  };
  const elements = Array.from(document.querySelectorAll('__INTERACTIVE_SELECTOR__'))
    .filter(visible)
    .slice(0, 250)
    .map((el) => {
      const rect = el.getBoundingClientRect();
      const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || '').trim().replace(/\s+/g, ' ');
      return {
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || '',
        text,
        attributes: attrs(el),
        css_path: cssPath(el),
        xpath: xpath(el),
        bounds: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) }
      };
    });
  const links = Array.from(document.querySelectorAll('a[href]'))
    .filter(visible)
    .map((el) => ({ href: el.href, text: (el.innerText || el.getAttribute('aria-label') || el.title || '').trim().replace(/\s+/g, ' ') }))
    .slice(0, 200);
  return {
    title: document.title || '',
    url: location.href,
    body_text: (document.body ? document.body.innerText : '').replace(/\s+/g, ' ').trim().slice(0, 5000),
    elements,
    links
  };
}
""".replace('__INTERACTIVE_SELECTOR__', INTERACTIVE_SELECTOR.replace('\\', '\\\\').replace("'", "\\'"))


def build_crawl_options(data, project):
    start_url = normalize_url(data.get('start_url') or project.base_url)
    return CrawlOptions(
        start_url=start_url,
        login_url=normalize_url(data.get('login_url') or data.get('start_url') or project.base_url),
        extra_start_urls=normalize_extra_start_urls(data.get('extra_start_urls') or data.get('seed_urls') or data.get('entry_urls')),
        username=str(data.get('username') or ''),
        password=str(data.get('password') or ''),
        username_selector=str(data.get('username_selector') or ''),
        password_selector=str(data.get('password_selector') or ''),
        submit_selector=str(data.get('submit_selector') or ''),
        max_pages=max(1, min(int(data.get('max_pages') or 30), 1000)),
        max_depth=max(1, min(int(data.get('max_depth') or 3), 10)),
        max_actions=max(1, min(int(data.get('max_actions') or 1000), 10000)),
        max_actions_per_page=max(1, min(int(data.get('max_actions_per_page') or 80), 300)),
        timeout_minutes=max(1, min(int(data.get('timeout_minutes') or 180), 1440)),
        retry_count=max(0, min(int(data.get('retry_count') or 1), 5)),
        allow_destructive_actions=bool(data.get('allow_destructive_actions', False)),
        headless=bool(data.get('headless', True)),
        sync_elements=bool(data.get('sync_elements', True)),
    )


def normalize_extra_start_urls(value):
    if not value:
        return ()
    if isinstance(value, str):
        raw_items = re.split(r'[\r\n,]+', value)
    elif isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = [value]
    urls = []
    seen = set()
    for item in raw_items:
        url = normalize_url(item)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return tuple(urls)


def crawl_config_from_options(options):
    return {
        'max_pages': options.max_pages,
        'max_depth': options.max_depth,
        'max_actions': options.max_actions,
        'max_actions_per_page': options.max_actions_per_page,
        'timeout_minutes': options.timeout_minutes,
        'retry_count': options.retry_count,
        'allow_destructive_actions': options.allow_destructive_actions,
        'headless': options.headless,
        'sync_elements': options.sync_elements,
        'extra_start_urls': list(options.extra_start_urls or ()),
        'username_selector': options.username_selector,
        'password_selector': options.password_selector,
        'submit_selector': options.submit_selector,
        'username': options.username,
        'password': options.password,
        'has_username': bool(options.username),
        'has_password': bool(options.password),
    }


def create_page_graph(project, user, data):
    graph, options = prepare_page_graph(project, user, data)
    run_graph_crawl(graph.id, options)
    return graph


def start_page_graph_crawl(project, user, data):
    close_old_connections()
    graph, options = prepare_page_graph(project, user, data)
    PAGE_GRAPH_EXECUTOR.submit(run_graph_crawl, graph.id, options)
    return graph


def resume_page_graph_crawl(graph, data=None):
    payload = dict(graph.crawl_config or {})
    payload.update(data or {})
    preserve_saved_credentials(payload, graph.crawl_config or {})
    payload.setdefault('start_url', graph.start_url)
    payload.setdefault('login_url', graph.login_url or graph.start_url)
    options = build_crawl_options(payload, graph.project)
    coverage_status = str((graph.progress or {}).get('coverage_status') or (graph.summary or {}).get('coverage', {}).get('coverage_status') or '')
    pending_state_count = int((graph.progress or {}).get('pending_state_count') or (graph.progress or {}).get('queued_count') or 0)
    can_resume_completed = graph.status == 'completed' and (
        coverage_status in {'limited', 'incomplete'} or pending_state_count > 0 or has_new_resume_seed(graph, options)
    )
    if graph.status not in {'failed', 'timeout', 'cancelled'} and not can_resume_completed:
        raise ValueError('只有失败、超时、已取消、覆盖未完成，或提交了新入口 URL 的页面图谱可以继续爬取')
    update_graph_status(
        graph.id,
        status='pending',
        error_message='',
        completed_at=None,
        progress=initial_graph_progress(options),
        crawl_config=crawl_config_from_options(options),
        start_url=options.start_url,
        login_url=options.login_url,
    )
    PAGE_GRAPH_EXECUTOR.submit(run_graph_crawl, graph.id, options, True)
    return graph


def prepare_page_graph(project, user, data):
    options = build_crawl_options(data, project)
    graph = UIPageGraph.objects.create(
        project=project,
        name=str(data.get('name') or f'{project.name} 页面图谱 {datetime.now().strftime("%Y%m%d%H%M")}')[:200],
        start_url=options.start_url,
        login_url=options.login_url,
        crawl_config=crawl_config_from_options(options),
        progress=initial_graph_progress(options),
        crawl_state={},
        created_by=user,
    )
    return graph, options


def preserve_saved_credentials(payload, saved_config):
    if not str(payload.get('username') or '').strip() and saved_config.get('username'):
        payload['username'] = saved_config.get('username')
    if not str(payload.get('password') or '').strip() and saved_config.get('password'):
        payload['password'] = saved_config.get('password')


def has_new_resume_seed(graph, options):
    existing_keys = set(
        UIPageNode.objects.filter(graph=graph)
        .values_list('route_key', flat=True)
    )
    existing_urls = set(
        UIPageNode.objects.filter(graph=graph)
        .values_list('url', flat=True)
    )
    base_url = graph.project.base_url if graph.project else options.start_url
    for url in [options.start_url, *(options.extra_start_urls or ())]:
        normalized = normalize_url(url)
        if not normalized:
            continue
        if base_url and not same_origin(normalized, base_url):
            continue
        if normalized not in existing_urls and route_key_for_url(normalized) not in existing_keys:
            return True
    return False


def run_graph_crawl(graph_id, options, resume=False):
    close_old_connections()
    graph = UIPageGraph.objects.select_related('project').get(id=graph_id)
    started_at = timezone.now()
    update_graph_status(
        graph_id,
        status='running',
        started_at=started_at,
        heartbeat_at=started_at,
        completed_at=None,
        error_message='',
        progress=initial_graph_progress(options, started_at=started_at),
    )
    graph.started_at = started_at
    graph.heartbeat_at = started_at
    graph.completed_at = None

    try:
        summary = crawl_project_graph(graph, options, resume=resume)
        completed_at = timezone.now()
        update_graph_status(
            graph_id,
            status='completed',
            summary=summary,
            completed_at=completed_at,
            heartbeat_at=completed_at,
            progress=final_graph_progress(graph_id, options, status='completed', summary=summary),
        )
    except Exception as exc:
        logger.exception('UI page graph crawl failed for graph %s', graph_id)
        if isinstance(exc, PageGraphCrawlCancelled):
            status = 'cancelled'
        elif isinstance(exc, PageGraphCrawlTimeout):
            status = 'timeout'
        else:
            status = 'failed'
        completed_at = timezone.now()
        update_graph_status(
            graph_id,
            status=status,
            error_message=str(exc),
            completed_at=completed_at,
            heartbeat_at=completed_at,
            progress=final_graph_progress(graph_id, options, status=status, error_message=str(exc)),
        )
        if not isinstance(exc, PageGraphCrawlCancelled):
            raise
    finally:
        close_old_connections()


def crawl_project_graph(graph, options, resume=False):
    os.environ.setdefault('CRAWL4_AI_BASE_DIRECTORY', os.path.abspath(os.path.join(os.getcwd(), 'tmp', 'crawl4ai_home')))
    try:
        import crawl4ai  # noqa: F401
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError as exc:
        raise RuntimeError('页面图谱爬取需要安装 crawl4ai：python -m pip install crawl4ai') from exc

    return run_crawl4ai_project_graph(graph, options, AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, resume=resume)


def run_crawl4ai_project_graph(graph, options, AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, resume=False):
    import asyncio

    return asyncio.run(
        crawl_project_graph_async(
            graph,
            options,
            AsyncWebCrawler,
            BrowserConfig,
            CrawlerRunConfig,
            resume=resume,
        )
    )


async def run_login_with_heartbeat(crawler, CrawlerRunConfig, graph, options, session_id, base_url, db):
    import asyncio

    login_started_at = timezone.now()
    login_timeout_seconds = login_timeout_seconds_for_options(options)
    task = asyncio.create_task(
        crawl4ai_login_and_snapshot(
            crawler,
            CrawlerRunConfig,
            options,
            session_id,
            base_url,
        )
    )
    while not task.done():
        elapsed_seconds = int((timezone.now() - login_started_at).total_seconds())
        if elapsed_seconds >= login_timeout_seconds:
            message = f'页面图谱登录阶段超过 {login_timeout_seconds} 秒未完成，已自动终止，请检查登录地址、账号密码或登录按钮选择器'
            task.cancel()
            db(
                update_graph_progress,
                graph.id,
                stage='login',
                current_url=options.login_url or options.start_url,
                login_elapsed_seconds=elapsed_seconds,
                login_timeout_seconds=login_timeout_seconds,
                error_message=message,
            )
            raise PageGraphCrawlTimeout(message)
        db(
            update_graph_progress,
            graph.id,
            stage='login',
            current_url=options.login_url or options.start_url,
            login_elapsed_seconds=elapsed_seconds,
            login_timeout_seconds=login_timeout_seconds,
        )
        wait_seconds = max(1, min(PAGE_GRAPH_LOGIN_HEARTBEAT_SECONDS, login_timeout_seconds - elapsed_seconds))
        done, _ = await asyncio.wait({task}, timeout=wait_seconds)
        if done:
            break
    try:
        return await task
    except asyncio.CancelledError as exc:
        raise PageGraphCrawlTimeout('页面图谱登录阶段已被取消') from exc


async def crawl_project_graph_async(graph, options, AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, resume=False):
    project = graph.project
    base_url = normalize_url(project.base_url or options.start_url)
    visited = set()
    queued = set()
    queue = deque()
    nodes_by_key = {}
    clicked_actions = set()
    extracted_elements = 0
    synced_elements = 0
    failed_actions = 0
    started_at = graph.started_at or timezone.now()
    current_depth = 0

    browser_config = BrowserConfig(headless=options.headless, verbose=False)
    session_id = f'page-graph-{graph.id}-{uuid4().hex[:8]}'
    with DbThreadRunner() as db:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            db(update_graph_progress, graph.id, stage='login', current_url=options.login_url or options.start_url)
            entry_snapshot = await run_login_with_heartbeat(
                crawler,
                CrawlerRunConfig,
                graph,
                options,
                session_id,
                base_url,
                db,
            )
            entry_url = normalize_url(entry_snapshot.get('url') or options.start_url)
            entry_key = state_key_for_snapshot(entry_snapshot)
            entry_snapshot['state_key'] = entry_key
            seed_queue = await build_seed_queue(
                crawler,
                CrawlerRunConfig,
                options,
                session_id,
                base_url,
                entry_snapshot,
            )
            if resume:
                existing_queue, existing_clicked = await rebuild_resume_queue(
                    graph,
                    CrawlerRunConfig,
                    crawler,
                    session_id,
                    options,
                    base_url,
                    db,
                )
                clicked_actions.update(existing_clicked)
                for item in existing_queue:
                    queued.add(item[0].get('state_key') or state_key_for_snapshot(item[0]))
                    queue.append(item)
                for item in seed_queue:
                    seed_key = item[0].get('state_key') or state_key_for_snapshot(item[0])
                    if seed_key not in queued:
                        queued.add(seed_key)
                        queue.append(item)
                if not queue:
                    queued.add(entry_key)
                    queue.append((entry_snapshot, 0, None, [], entry_url))
            else:
                for item in seed_queue:
                    seed_key = item[0].get('state_key') or state_key_for_snapshot(item[0])
                    if seed_key not in queued:
                        queued.add(seed_key)
                        queue.append(item)
                if not queue:
                    queued.add(entry_key)
                    queue.append((entry_snapshot, 0, None, [], entry_url))
            pending_keys = queued - visited
            db(
                update_graph_crawl_state,
                graph.id,
                queued=list(queued)[-500:],
                discovered=list(queued)[-5000:],
                visited=[],
                pending=list(pending_keys)[-5000:],
                clicked_actions=list(clicked_actions)[-2000:],
                coverage=build_coverage_snapshot(
                    queued,
                    visited,
                    pending_keys,
                    len(clicked_actions),
                    failed_actions,
                    options,
                    status='running',
                ),
            )

            while queue and len(visited) < options.max_pages:
                db(ensure_graph_not_cancelled, graph.id)
                ensure_graph_not_timed_out(started_at, options)
                snapshot, depth, source_edge, action_path, action_entry_url = queue.popleft()
                current_depth = depth
                current_url = normalize_url(snapshot.get('url') or '')
                current_key = state_key_for_snapshot(snapshot)
                snapshot['state_key'] = current_key
                snapshot['depth'] = depth
                if current_key in visited or not same_origin(current_url, base_url):
                    continue
                visited.add(current_key)
                pending_keys = queued - visited
                running_coverage = build_coverage_snapshot(
                    queued,
                    visited,
                    pending_keys,
                    len(clicked_actions),
                    failed_actions,
                    options,
                    status='running',
                )
                db(
                    update_graph_progress,
                    graph.id,
                    stage='crawling',
                    current_url=current_url,
                    visited_count=len(visited),
                    queued_count=len(pending_keys),
                    discovered_state_count=len(queued),
                    visited_state_count=len(visited),
                    pending_state_count=len(pending_keys),
                    clicked_count=len(clicked_actions),
                    failed_action_count=failed_actions,
                    element_count=extracted_elements,
                    synced_element_count=synced_elements,
                    coverage_status=running_coverage['coverage_status'],
                    coverage_message=running_coverage['coverage_message'],
                    termination_reason=running_coverage['termination_reason'],
                    max_pages_reached=running_coverage['max_pages_reached'],
                    max_actions_reached=running_coverage['max_actions_reached'],
                )

                node = db(upsert_page_node, graph, project, snapshot)
                nodes_by_key[current_key] = node

                if source_edge and source_edge.get('source_node'):
                    db(create_page_edge, graph, project, source_edge['source_node'], node, source_edge)

                for item in snapshot.get('elements') or []:
                    element_payload = build_page_element_payload_from_snapshot(node, item)
                    if not element_payload:
                        continue
                    graph_element, synced = db(
                        persist_page_element,
                        graph,
                        project,
                        node,
                        element_payload,
                        options.sync_elements,
                    )
                    if graph_element:
                        extracted_elements += 1
                        if synced:
                            synced_elements += 1

                if depth >= options.max_depth:
                    continue

                page_action_count = 0
                for action in discover_graph_actions(snapshot, current_url, base_url, options.allow_destructive_actions):
                    db(ensure_graph_not_cancelled, graph.id)
                    ensure_graph_not_timed_out(started_at, options)
                    if len(clicked_actions) >= options.max_actions or page_action_count >= options.max_actions_per_page:
                        break
                    action_key = action_fingerprint(current_key, action)
                    if action_key in clicked_actions:
                        continue
                    clicked_actions.add(action_key)
                    page_action_count += 1
                    try:
                        target_snapshot = await crawl4ai_click_action_with_retry(
                            crawler,
                            CrawlerRunConfig,
                            action_entry_url,
                            action_path,
                            action,
                            session_id,
                            options.timeout_ms,
                            options.retry_count,
                        )
                    except Exception as exc:
                        failed_actions += 1
                        logger.warning('Page graph action failed graph=%s url=%s action=%s error=%s', graph.id, current_url, action, exc)
                        pending_keys = queued - visited
                        db(
                            update_graph_progress,
                            graph.id,
                            stage='crawling',
                            current_url=current_url,
                            visited_count=len(visited),
                            queued_count=len(pending_keys),
                            discovered_state_count=len(queued),
                            visited_state_count=len(visited),
                            pending_state_count=len(pending_keys),
                            clicked_count=len(clicked_actions),
                            failed_action_count=failed_actions,
                            last_error=str(exc),
                        )
                        continue
                    target_url = normalize_url(target_snapshot.get('url') or '')
                    if not target_url or not same_origin(target_url, base_url):
                        continue
                    target_key = state_key_for_snapshot(target_snapshot)
                    target_snapshot['state_key'] = target_key
                    target_state_key = route_key_for_url(target_url)
                    edge_payload = {
                        'source_node': node,
                        'trigger_text': action.get('text') or action.get('name') or '',
                        'locator_strategy': action.get('locator_strategy') or '',
                        'locator_value': action.get('locator_value') or '',
                        'keywords': extract_keywords(action.get('text'), action.get('name'), target_state_key),
                        'metadata': {
                            'crawl4ai_action': action,
                            'target_state_key': target_key,
                            'action_category': action.get('category') or 'unknown',
                        },
                    }
                    if target_key == current_key:
                        continue
                    if target_key in visited:
                        target_node = nodes_by_key.get(target_key)
                        if target_node:
                            db(create_page_edge, graph, project, node, target_node, edge_payload)
                        continue
                    if target_key in queued:
                        continue
                    queued.add(target_key)
                    pending_keys = queued - visited
                    queue.append((
                        target_snapshot,
                        depth + 1,
                        edge_payload,
                        action_path + [action],
                        action_entry_url,
                    ))
                    db(
                        update_graph_progress,
                        graph.id,
                        stage='crawling',
                        current_url=current_url,
                        visited_count=len(visited),
                        queued_count=len(pending_keys),
                        discovered_state_count=len(queued),
                        visited_state_count=len(visited),
                        pending_state_count=len(pending_keys),
                        clicked_count=len(clicked_actions),
                        failed_action_count=failed_actions,
                    )
                pending_keys = queued - visited
                running_coverage = build_coverage_snapshot(
                    queued,
                    visited,
                    pending_keys,
                    len(clicked_actions),
                    failed_actions,
                    options,
                    status='running',
                )
                db(
                    update_graph_crawl_state,
                    graph.id,
                    queued=list(queued)[-500:],
                    discovered=list(queued)[-5000:],
                    visited=list(visited)[-5000:],
                    pending=list(pending_keys)[-5000:],
                    clicked_actions=list(clicked_actions)[-2000:],
                    current_depth=depth,
                    coverage=running_coverage,
                )

        pending_keys = queued - visited
        final_coverage = build_coverage_snapshot(
            queued,
            visited,
            pending_keys,
            len(clicked_actions),
            failed_actions,
            options,
            status='completed',
        )
        db(
            update_graph_crawl_state,
            graph.id,
            queued=list(queued)[-500:],
            discovered=list(queued)[-5000:],
            visited=list(visited)[-5000:],
            pending=list(pending_keys)[-5000:],
            clicked_actions=list(clicked_actions)[-2000:],
            current_depth=current_depth,
            coverage=final_coverage,
        )
        db(
            update_graph_progress,
            graph.id,
            stage='completed',
            status='completed',
            visited_count=len(visited),
            queued_count=len(pending_keys),
            discovered_state_count=len(queued),
            visited_state_count=len(visited),
            pending_state_count=len(pending_keys),
            clicked_count=len(clicked_actions),
            failed_action_count=failed_actions,
            coverage_status=final_coverage['coverage_status'],
            coverage_message=final_coverage['coverage_message'],
            termination_reason=final_coverage['termination_reason'],
            max_pages_reached=final_coverage['max_pages_reached'],
            max_actions_reached=final_coverage['max_actions_reached'],
        )
        return db(build_crawl_summary, graph, extracted_elements, synced_elements, options, final_coverage)


def build_crawl_summary(graph, extracted_elements, synced_elements, options, coverage=None):
    return {
        'pages': UIPageNode.objects.filter(graph=graph).count(),
        'elements': extracted_elements,
        'synced_elements': synced_elements,
        'edges': UIPageEdge.objects.filter(graph=graph).count(),
        'max_pages': options.max_pages,
        'max_depth': options.max_depth,
        'coverage': coverage or {},
    }


async def crawl4ai_login_and_snapshot(crawler, CrawlerRunConfig, options, session_id, base_url):
    login_js = build_login_js(options)
    config = CrawlerRunConfig(
        session_id=session_id,
        js_code=login_js,
        wait_for='css:body',
        page_timeout=options.timeout_ms,
        delay_before_return_html=1.5,
        scan_full_page=True,
    )
    result = await crawler.arun(url=options.login_url or options.start_url, config=config)
    snapshot = crawl4ai_result_to_snapshot(result)
    current_url = normalize_url(snapshot.get('url') or '')
    if is_login_url(current_url) or snapshot_looks_like_login(snapshot):
        raise ValueError('自动登录失败：提交后仍停留在登录页，请检查账号密码或填写登录按钮 CSS 选择器')
    if not same_origin(current_url, base_url):
        raise ValueError(f'自动登录失败：登录后跳转到非同源地址 {current_url}')
    return snapshot


def snapshot_looks_like_login(snapshot):
    elements = snapshot.get('elements') or []
    body_text = normalize_keyword_text(snapshot.get('body_text') or '')
    has_password = any((item.get('attributes') or {}).get('type') == 'password' for item in elements)
    has_login_text = any(keyword in body_text for keyword in ('登录', '登陆', '忘记密码', 'login', 'signin'))
    return has_password or has_login_text


async def crawl4ai_snapshot_url(crawler, CrawlerRunConfig, url, session_id, timeout_ms):
    config = CrawlerRunConfig(
        session_id=session_id,
        wait_for='css:body',
        page_timeout=timeout_ms,
        delay_before_return_html=0.8,
        scan_full_page=True,
    )
    result = await crawler.arun(url=url, config=config)
    return crawl4ai_result_to_snapshot(result)


async def crawl4ai_click_action(crawler, CrawlerRunConfig, source_url, action, session_id, timeout_ms):
    script = build_click_action_js(action)
    config = CrawlerRunConfig(
        session_id=session_id,
        js_code=script,
        js_only=True,
        wait_for='css:body',
        page_timeout=timeout_ms,
        delay_before_return_html=1.5,
        scan_full_page=True,
    )
    result = await crawler.arun(url=source_url, config=config)
    return crawl4ai_result_to_snapshot(result)


def crawl4ai_result_to_snapshot(result):
    url = normalize_url(getattr(result, 'url', '') or '')
    html = getattr(result, 'html', '') or getattr(result, 'cleaned_html', '') or ''
    if not html and hasattr(result, 'fit_markdown'):
        html = str(getattr(result, 'fit_markdown') or '')
    return html_to_snapshot(html, url)


def html_to_snapshot(html, url):
    soup = BeautifulSoup(html or '', 'html.parser')
    title = compact_text(soup.title.get_text(' ', strip=True) if soup.title else '', 300)
    body = soup.body or soup
    elements = []
    for tag in body.select('a[href], button, input, textarea, select, [role="button"], [role="link"], [role="menuitem"], [role="tab"], [onclick], [data-testid], [data-test]')[:350]:
        text = compact_text(tag.get_text(' ', strip=True) or tag.get('value') or tag.get('aria-label') or tag.get('placeholder') or tag.get('title'), 200)
        attrs = {
            key: tag.get(key)
            for key in ['id', 'class', 'name', 'type', 'placeholder', 'aria-label', 'title', 'role', 'href', 'data-testid', 'data-test', 'data-cy', 'data-qa']
            if tag.get(key)
        }
        if isinstance(attrs.get('class'), list):
            attrs['class'] = ' '.join(attrs['class'])
        elements.append({
            'tag': tag.name,
            'role': tag.get('role') or '',
            'text': text,
            'attributes': attrs,
            'css_path': stable_soup_css_selector(tag),
            'xpath': stable_soup_xpath(tag),
            'bounds': {},
        })
    links = [
        {'href': urljoin(url, tag.get('href') or ''), 'text': compact_text(tag.get_text(' ', strip=True), 200)}
        for tag in body.select('a[href]')[:250]
    ]
    return {
        'title': title,
        'url': url,
        'body_text': compact_text(body.get_text(' ', strip=True), 5000),
        'elements': elements,
        'links': links,
    }


def stable_soup_css_selector(tag):
    tag_name = tag.name or '*'
    test_id = tag.get('data-testid')
    if is_stable_attribute_value(test_id):
        return f'{tag_name}[data-testid="{css_escape(test_id)}"]'
    name = tag.get('name')
    if is_stable_attribute_value(name):
        return f'{tag_name}[name="{css_escape(name)}"]'
    element_id = tag.get('id')
    if is_stable_attribute_value(element_id):
        return f'#{css_escape(element_id)}'
    placeholder = tag.get('placeholder')
    if is_stable_attribute_value(placeholder):
        return f'{tag_name}[placeholder="{css_escape(placeholder)}"]'
    class_value = tag.get('class') or []
    if isinstance(class_value, str):
        class_value = re.split(r'\s+', class_value)
    stable_classes = [item for item in class_value if item and not VOLATILE_CLASS_RE.search(item) and is_stable_attribute_value(item)][:2]
    if stable_classes:
        return f'{tag_name}.' + '.'.join(css_escape(item) for item in stable_classes)
    return ''


def stable_soup_xpath(tag):
    tag_name = tag.name or '*'
    text = compact_text(tag.get_text(' ', strip=True), 80)
    if text and is_stable_attribute_value(text):
        return f'//{tag_name}[normalize-space(.)={xpath_literal(text)}]'
    for attr in ['aria-label', 'placeholder', 'title', 'name']:
        value = tag.get(attr)
        if is_stable_attribute_value(value):
            return f'//{tag_name}[@{attr}={xpath_literal(value)}]'
    return ''


def build_login_js(options):
    return f"""
(async () => {{
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const visible = (el) => {{
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && !el.disabled;
  }};
  const first = (selectors) => {{
    for (const selector of selectors) {{
      if (!selector) continue;
      try {{
        const items = Array.from(document.querySelectorAll(selector));
        const found = items.find(visible);
        if (found) return found;
      }} catch (e) {{}}
    }}
    return null;
  }};
  const setValue = (el, value) => {{
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, value);
    else el.value = value;
    el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: value }}));
    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
  }};
  const username = first({json.dumps(login_username_selectors(options), ensure_ascii=False)});
  const password = first({json.dumps(login_password_selectors(options), ensure_ascii=False)});
  if (!password) throw new Error('未找到密码输入框');
  if ({json.dumps(bool(options.username))} && !username) throw new Error('未找到账号输入框');
  if (username) {{
    username.focus();
    setValue(username, {json.dumps(options.username, ensure_ascii=False)});
  }}
  password.focus();
  setValue(password, {json.dumps(options.password, ensure_ascii=False)});
  await sleep(500);
  const buttons = Array.from(document.querySelectorAll({json.dumps(login_button_selector(options), ensure_ascii=False)})).filter(visible);
  const button = buttons.find((el) => /登录|登陆|立即登录|login|sign\\s*in/i.test(el.innerText || el.value || '')) || buttons[0];
  if (button) {{
    button.focus();
    button.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true }}));
    button.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true }}));
    button.click();
  }} else {{
    password.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
    password.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
  }}
  await sleep(4000);
}})();
"""


def login_username_selectors(options):
    selectors = [options.username_selector] if options.username_selector else []
    selectors.extend([
        'input[name="username"]', 'input[name="user"]', 'input[name="userName"]', 'input[name="account"]',
        'input[name="loginName"]', 'input[name="phone"]', 'input[name="mobile"]',
        'input[autocomplete="username"]', 'input[placeholder*="账号"]', 'input[placeholder*="用户"]',
        'input[placeholder*="用户名"]', 'input[placeholder*="手机"]', 'input[placeholder*="邮箱"]',
        'input[placeholder*="username" i]', 'input[placeholder*="account" i]', 'input[placeholder*="email" i]',
        'input[type="text"]', 'input:not([type])',
    ])
    return [item for item in selectors if item]


def login_password_selectors(options):
    selectors = [options.password_selector] if options.password_selector else []
    selectors.extend([
        'input[type="password"]', 'input[name="password"]', 'input[autocomplete="current-password"]',
        'input[placeholder*="密码"]', 'input[placeholder*="password" i]',
    ])
    return [item for item in selectors if item]


def login_button_selector(options):
    selectors = [options.submit_selector] if options.submit_selector else []
    selectors.extend([
        'button[type="submit"]', 'input[type="submit"]', 'button', '[role="button"]',
        '.login button', '.login-form button', 'form button',
    ])
    return ','.join(item for item in selectors if item)


def discover_graph_actions(snapshot, current_url, base_url):
    actions = []
    for link in discover_navigation_links(snapshot, current_url, base_url):
        actions.append({
            'text': link.get('text') or '',
            'name': link.get('text') or '',
            'locator_strategy': 'text' if link.get('text') else '',
            'locator_value': compact_text(link.get('text'), 200) if link.get('text') else '',
            'href': link.get('href') or '',
            'kind': 'link',
        })
    for item in snapshot.get('elements') or []:
        text = compact_text(item.get('text') or (item.get('attributes') or {}).get('aria-label'), 120)
        if not text or DANGEROUS_TEXT_RE.search(text):
            continue
        role = str(item.get('role') or '').lower()
        tag = str(item.get('tag') or '').lower()
        if tag not in {'a', 'button'} and role not in {'button', 'link', 'menuitem', 'tab'}:
            continue
        candidates = build_locator_candidates(item)
        best = sorted(candidates, key=score_locator, reverse=True)[0] if candidates else None
        if not best:
            continue
        actions.append({
            'text': text,
            'name': text,
            'locator_strategy': locator_name_for_strategy(best.get('strategy')),
            'locator_value': best.get('value'),
            'href': (item.get('attributes') or {}).get('href') or '',
            'kind': 'click',
        })
    seen = set()
    unique = []
    for action in actions:
        key = (action.get('text'), action.get('locator_strategy'), action.get('locator_value'), action.get('href'))
        if key not in seen:
            seen.add(key)
            unique.append(action)
    return unique[:80]


def action_fingerprint(source_url, action):
    return '|'.join([
        route_key_for_url(source_url),
        str(action.get('kind') or ''),
        str(action.get('locator_strategy') or ''),
        str(action.get('locator_value') or ''),
        str(action.get('href') or ''),
    ])


def build_click_action_js(action):
    if action.get('href'):
        return f"window.location.href = {json.dumps(action['href'], ensure_ascii=False)};"
    strategy = str(action.get('locator_strategy') or '').lower()
    value = action.get('locator_value') or ''
    text = action.get('text') or action.get('name') or ''
    return f"""
(async () => {{
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const visible = (el) => {{
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && !el.disabled;
  }};
  let elements = [];
  const strategy = {json.dumps(strategy)};
  const value = {json.dumps(value, ensure_ascii=False)};
  const text = {json.dumps(text, ensure_ascii=False)};
  try {{
    if (strategy === 'id') elements = Array.from(document.querySelectorAll('#' + CSS.escape(value)));
    else if (strategy === 'name') elements = Array.from(document.querySelectorAll('[name="' + CSS.escape(value) + '"]'));
    else if (strategy === 'placeholder') elements = Array.from(document.querySelectorAll('[placeholder="' + value.replace(/"/g, '\\\\"') + '"]'));
    else if (strategy === 'test-id') elements = Array.from(document.querySelectorAll('[data-testid="' + CSS.escape(value) + '"]'));
    else if (strategy === 'css') elements = Array.from(document.querySelectorAll(value));
  }} catch (e) {{}}
  if (!elements.length && text) {{
    elements = Array.from(document.querySelectorAll('a,button,[role="button"],[role="link"],[role="menuitem"],[role="tab"]')).filter((el) => (el.innerText || el.value || '').trim() === text);
  }}
  const target = elements.find(visible) || elements[0];
  if (target) target.click();
  await sleep(1800);
}})();
"""


def state_key_for_snapshot(snapshot):
    url = normalize_url(snapshot.get('url') or '')
    route_key = route_key_for_url(url) or '/'
    body_text = normalize_keyword_text(snapshot.get('body_text') or '')
    body_text = re.sub(r'\d{4,}', '', body_text)
    element_bits = []
    for item in (snapshot.get('elements') or [])[:160]:
        attrs = item.get('attributes') or {}
        stable_attrs = []
        for attr in ('data-testid', 'data-test', 'data-cy', 'name', 'aria-label', 'placeholder', 'title', 'href'):
            value = attrs.get(attr)
            if value and is_stable_attribute_value(value):
                stable_attrs.append(f'{attr}={value}')
        element_bits.append('|'.join([
            str(item.get('tag') or ''),
            str(item.get('role') or ''),
            compact_text(item.get('text'), 80),
            ';'.join(stable_attrs),
        ]))
    digest_source = '\n'.join([
        route_key,
        compact_text(snapshot.get('title'), 200),
        compact_text(body_text, 1800),
        '\n'.join(element_bits),
    ])
    digest = hashlib.sha1(digest_source.encode('utf-8', errors='ignore')).hexdigest()[:12]
    return f'{route_key}::state:{digest}'[:500]


def build_snapshot_js():
    return f"""
const __pageGraphSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
await __pageGraphSleep(1000);
return {{ snapshot: await ({page_extract_script()})() }};
"""


async def crawl4ai_login_and_snapshot(crawler, CrawlerRunConfig, options, session_id, base_url):
    config = CrawlerRunConfig(
        session_id=session_id,
        js_code=build_login_js(options),
        wait_for='css:body',
        page_timeout=options.timeout_ms,
        wait_for_timeout=options.timeout_ms,
        delay_before_return_html=0.2,
        scan_full_page=True,
        simulate_user=True,
    )
    result = await crawler.arun(url=options.login_url or options.start_url, config=config)
    error = extract_js_error(result)
    if error:
        raise ValueError(f'自动登录失败：{error}')
    snapshot = crawl4ai_result_to_snapshot(result)
    current_url = normalize_url(snapshot.get('url') or '')
    logger.info(
        'Page graph crawl4ai login snapshot url=%s title=%s elements=%s text=%s',
        current_url,
        snapshot.get('title'),
        len(snapshot.get('elements') or []),
        compact_text(snapshot.get('body_text'), 200),
    )
    if (options.username or options.password) and (is_login_url(current_url) or snapshot_looks_like_login(snapshot)):
        raise ValueError(
            '提交后仍停留在登录页。请检查账号密码，或填写账号输入框、密码输入框、登录按钮 CSS 选择器。'
        )
    if not same_origin(current_url, base_url):
        raise ValueError(f'登录后跳转到非同源地址 {current_url}')
    return snapshot


def snapshot_looks_like_login(snapshot):
    elements = snapshot.get('elements') or []
    body_text = normalize_keyword_text(snapshot.get('body_text') or '')
    has_password = any((item.get('attributes') or {}).get('type') == 'password' for item in elements)
    has_login_text = any(keyword in body_text for keyword in ('登录', '登陆', '忘记密码', 'login', 'signin'))
    return has_password or has_login_text


async def crawl4ai_snapshot_url(crawler, CrawlerRunConfig, url, session_id, timeout_ms):
    config = CrawlerRunConfig(
        session_id=session_id,
        js_code=build_snapshot_js(),
        wait_for='css:body',
        page_timeout=timeout_ms,
        wait_for_timeout=timeout_ms,
        delay_before_return_html=0.2,
        scan_full_page=True,
    )
    result = await crawler.arun(url=url, config=config)
    return crawl4ai_result_to_snapshot(result)


async def build_seed_queue(crawler, CrawlerRunConfig, options, session_id, base_url, entry_snapshot):
    seeds = []
    seen = set()
    entry_url = normalize_url(entry_snapshot.get('url') or options.start_url)
    for url in [entry_url, options.start_url, *(options.extra_start_urls or ())]:
        normalized = normalize_url(url)
        if not normalized or normalized in seen or not same_origin(normalized, base_url):
            continue
        seen.add(normalized)
        if normalized == entry_url:
            snapshot = dict(entry_snapshot)
        else:
            try:
                snapshot = await crawl4ai_snapshot_url(crawler, CrawlerRunConfig, normalized, session_id, options.timeout_ms)
            except Exception as exc:
                logger.warning('Page graph seed snapshot failed url=%s error=%s', normalized, exc)
                continue
        state_key = state_key_for_snapshot(snapshot)
        snapshot['state_key'] = state_key
        seeds.append((snapshot, 0, None, [], normalize_url(snapshot.get('url') or normalized)))
    return seeds


async def rebuild_resume_queue(graph, CrawlerRunConfig, crawler, session_id, options, base_url, db):
    existing_clicked = db(load_existing_action_fingerprints, graph.id)
    queue = []
    nodes = db(load_resume_seed_nodes, graph.id, options.max_pages)
    for node in nodes:
        url = normalize_url(node.get('url') or '')
        if not url or not same_origin(url, base_url):
            continue
        try:
            snapshot = await crawl4ai_snapshot_url(crawler, CrawlerRunConfig, url, session_id, options.timeout_ms)
        except Exception as exc:
            logger.warning('Page graph resume snapshot failed graph=%s url=%s error=%s', graph.id, url, exc)
            continue
        state_key = state_key_for_snapshot(snapshot)
        snapshot['state_key'] = state_key
        metadata = node.get('metadata') or {}
        depth = max(0, min(int(metadata.get('depth') or 0), options.max_depth))
        queue.append((snapshot, depth, None, [], normalize_url(snapshot.get('url') or url)))
    return queue, existing_clicked


def load_resume_seed_nodes(graph_id, max_pages):
    return list(
        UIPageNode.objects.filter(graph_id=graph_id)
        .order_by('id')
        .values('url', 'route_key', 'metadata')[:max_pages]
    )


def load_existing_action_fingerprints(graph_id):
    fingerprints = set()
    edges = UIPageEdge.objects.filter(graph_id=graph_id).select_related('source').only(
        'locator_strategy',
        'locator_value',
        'trigger_text',
        'metadata',
        'source__route_key',
        'source__url',
    )
    for edge in edges:
        action = {}
        metadata = edge.metadata or {}
        if isinstance(metadata.get('crawl4ai_action'), dict):
            action.update(metadata.get('crawl4ai_action'))
        action.setdefault('kind', action.get('kind') or 'click')
        action.setdefault('text', edge.trigger_text or action.get('text') or action.get('name') or '')
        action.setdefault('locator_strategy', edge.locator_strategy or action.get('locator_strategy') or '')
        action.setdefault('locator_value', edge.locator_value or action.get('locator_value') or '')
        action.setdefault('href', action.get('href') or '')
        source_keys = {
            edge.source.route_key or route_key_for_url(edge.source.url),
            (edge.source.metadata or {}).get('state_key') or '',
        }
        for source_key in source_keys:
            if source_key:
                fingerprints.add(action_fingerprint(source_key, action))
    return fingerprints


async def crawl4ai_click_action(crawler, CrawlerRunConfig, entry_url, action_path, action, session_id, timeout_ms):
    config = CrawlerRunConfig(
        session_id=session_id,
        js_code=build_replay_and_click_js(action_path, action),
        js_only=False,
        wait_for='css:body',
        page_timeout=timeout_ms,
        wait_for_timeout=timeout_ms,
        delay_before_return_html=0.2,
        scan_full_page=True,
        simulate_user=True,
    )
    result = await crawler.arun(url=entry_url, config=config)
    return crawl4ai_result_to_snapshot(result)


async def crawl4ai_click_action_with_retry(crawler, CrawlerRunConfig, entry_url, action_path, action, session_id, timeout_ms, retry_count):
    last_error = None
    for attempt in range(max(0, retry_count) + 1):
        try:
            return await crawl4ai_click_action(crawler, CrawlerRunConfig, entry_url, action_path, action, session_id, timeout_ms)
        except Exception as exc:
            last_error = exc
            if attempt >= retry_count:
                break
    raise last_error


def crawl4ai_result_to_snapshot(result):
    url = normalize_url(getattr(result, 'url', '') or '')
    js_snapshot = extract_js_snapshot(result)
    if js_snapshot:
        js_snapshot['url'] = normalize_url(js_snapshot.get('url') or url)
        return js_snapshot
    html = getattr(result, 'html', '') or getattr(result, 'cleaned_html', '') or ''
    if not html and hasattr(result, 'fit_markdown'):
        html = str(getattr(result, 'fit_markdown') or '')
    return html_to_snapshot(html, url)


def extract_js_error(result):
    if getattr(result, 'success', True) is False:
        return getattr(result, 'error_message', '') or 'crawl4ai 执行失败'
    execution = getattr(result, 'js_execution_result', None) or {}
    for item in execution.get('results') or []:
        if isinstance(item, dict) and item.get('success') is False:
            return item.get('error') or '页面脚本执行失败'
    return ''


def extract_js_snapshot(result):
    execution = getattr(result, 'js_execution_result', None) or {}
    for item in execution.get('results') or []:
        candidate = None
        if isinstance(item, dict) and item.get('snapshot'):
            candidate = item.get('snapshot')
        elif isinstance(item, dict) and isinstance(item.get('result'), dict) and item['result'].get('snapshot'):
            candidate = item['result'].get('snapshot')
        elif isinstance(item, dict) and {'url', 'elements'}.issubset(item.keys()):
            candidate = item
        if candidate:
            return normalize_snapshot_payload(candidate)
    return None


def normalize_snapshot_payload(snapshot):
    if not isinstance(snapshot, dict):
        return None
    elements = []
    for item in snapshot.get('elements') or []:
        if not isinstance(item, dict):
            continue
        attrs = item.get('attributes') or {}
        if not isinstance(attrs, dict):
            attrs = {}
        elements.append({
            'tag': str(item.get('tag') or '').lower(),
            'role': item.get('role') or attrs.get('role') or '',
            'text': compact_text(item.get('text'), 200),
            'attributes': attrs,
            'css_path': item.get('css_path') or '',
            'xpath': item.get('xpath') or '',
            'bounds': item.get('bounds') or {},
        })
    links = []
    for link in snapshot.get('links') or []:
        if isinstance(link, dict):
            links.append({
                'href': str(link.get('href') or ''),
                'text': compact_text(link.get('text'), 200),
            })
    return {
        'title': compact_text(snapshot.get('title'), 300),
        'url': normalize_url(snapshot.get('url') or ''),
        'body_text': compact_text(snapshot.get('body_text'), 5000),
        'elements': elements,
        'links': links,
    }


def build_login_js(options):
    if not options.username and not options.password:
        return build_snapshot_js()
    return f"""
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const visible = (el) => {{
  if (!el) return false;
  const style = getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && !el.disabled;
}};
const first = (selectors) => {{
  for (const selector of selectors) {{
    if (!selector) continue;
    try {{
      const found = Array.from(document.querySelectorAll(selector)).find(visible);
      if (found) return found;
    }} catch (e) {{}}
  }}
  return null;
}};
const textOf = (el) => (el?.innerText || el?.value || el?.getAttribute?.('aria-label') || el?.getAttribute?.('title') || '').trim();
const setValue = (el, value) => {{
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (setter) setter.call(el, value);
  else el.value = value;
  el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: value }}));
  el.dispatchEvent(new Event('change', {{ bubbles: true }}));
  el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
}};
const password = first({json.dumps(login_password_selectors(options), ensure_ascii=True)});
if (!password) throw new Error('未找到密码输入框');
const visibleInputs = Array.from(document.querySelectorAll('input,textarea'))
  .filter((el) => visible(el) && !['hidden','password','checkbox','radio','submit','button'].includes(String(el.type || '').toLowerCase()));
let username = first({json.dumps(login_username_selectors(options), ensure_ascii=True)});
if (!username) {{
  const passwordIndex = visibleInputs.findIndex((el) => {{
    const rect = el.getBoundingClientRect();
    const passRect = password.getBoundingClientRect();
    return rect.top <= passRect.top;
  }});
  username = passwordIndex >= 0 ? visibleInputs[passwordIndex] : visibleInputs[0];
}}
if ({json.dumps(bool(options.username))} && !username) throw new Error('未找到账号输入框');
if (username) {{
  username.focus();
  setValue(username, {json.dumps(options.username, ensure_ascii=True)});
}}
password.focus();
setValue(password, {json.dumps(options.password, ensure_ascii=True)});
await sleep(600);
const explicitButton = first({json.dumps([options.submit_selector] if options.submit_selector else [], ensure_ascii=True)});
const form = password.closest('form') || username?.closest('form');
const formButtons = form ? Array.from(form.querySelectorAll('button,input[type="submit"],[role="button"]')).filter(visible) : [];
const allButtons = Array.from(document.querySelectorAll({json.dumps(login_button_selector(options), ensure_ascii=True)})).filter(visible);
const loginText = /\\u767b\\u5f55|\\u767b\\u9304|login|sign\\s*in/i;
const button = explicitButton
  || formButtons.find((el) => loginText.test(textOf(el)))
  || allButtons.find((el) => loginText.test(textOf(el)))
  || formButtons[0]
  || allButtons[0];
const beforeUrl = location.href;
if (button) {{
  button.scrollIntoView({{ block: 'center', inline: 'center' }});
  button.focus();
  button.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }}));
  button.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window }}));
  button.click();
}} else {{
  password.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
  password.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
}}
const hasVisiblePassword = () => Array.from(document.querySelectorAll('input[type="password"]')).some(visible);
for (let i = 0; i < 60; i += 1) {{
  await sleep(250);
  if (!hasVisiblePassword()) break;
  if (location.href !== beforeUrl && !hasVisiblePassword()) break;
}}
await sleep(1500);
return {{ snapshot: await ({page_extract_script()})() }};
"""


def login_username_selectors(options):
    selectors = [options.username_selector] if options.username_selector else []
    selectors.extend([
        'input[name="username"]',
        'input[name="user"]',
        'input[name="userName"]',
        'input[name="account"]',
        'input[name="loginName"]',
        'input[autocomplete="username"]',
        'input[placeholder*="账号"]',
        'input[placeholder*="帐号"]',
        'input[placeholder*="用户"]',
        'input[placeholder*="username" i]',
        'input[placeholder*="account" i]',
        'input[type="text"]',
        'input:not([type])',
    ])
    return [item for item in selectors if item]


def login_password_selectors(options):
    selectors = [options.password_selector] if options.password_selector else []
    selectors.extend([
        'input[type="password"]',
        'input[name="password"]',
        'input[autocomplete="current-password"]',
        'input[placeholder*="密码"]',
        'input[placeholder*="password" i]',
    ])
    return [item for item in selectors if item]


def login_button_selector(options):
    selectors = [options.submit_selector] if options.submit_selector else []
    selectors.extend([
        'button[type="submit"]',
        'input[type="submit"]',
        'button',
        '[role="button"]',
        '.login button',
        '.login-form button',
        'form button',
    ])
    return ','.join(item for item in selectors if item)


def discover_graph_actions(snapshot, current_url, base_url, allow_destructive_actions=False):
    actions = []
    for link in discover_navigation_links(snapshot, current_url, base_url):
        text = compact_text(link.get('text'), 120)
        category = classify_graph_action(text, 'link')
        if category == 'destructive' and not allow_destructive_actions:
            continue
        actions.append({
            'text': text,
            'name': text,
            'locator_strategy': 'text' if text else '',
            'locator_value': text,
            'href': link.get('href') or '',
            'kind': 'link',
            'category': category,
        })
    for item in snapshot.get('elements') or []:
        attrs = item.get('attributes') or {}
        text = compact_text(item.get('text') or attrs.get('aria-label') or attrs.get('title') or attrs.get('placeholder'), 120)
        category = classify_graph_action(text, item.get('tag') or item.get('role') or '')
        if category == 'destructive' and not allow_destructive_actions:
            continue
        role = str(item.get('role') or '').lower()
        tag = str(item.get('tag') or '').lower()
        if tag not in {'a', 'button'} and role not in {'button', 'link', 'menuitem', 'tab', 'treeitem', 'option'}:
            continue
        candidates = build_locator_candidates(item)
        best = sorted(candidates, key=score_locator, reverse=True)[0] if candidates else None
        if not best:
            continue
        href = attrs.get('href') or ''
        resolved_href = ''
        if href and not str(href).lower().startswith('javascript:'):
            resolved = normalize_url(urljoin(current_url, href))
            if resolved and same_origin(resolved, base_url) and resolved != normalize_url(current_url):
                resolved_href = resolved
        actions.append({
            'text': text,
            'name': text or attrs.get('name') or attrs.get('aria-label') or attrs.get('title') or tag,
            'locator_strategy': locator_name_for_strategy(best.get('strategy')),
            'locator_value': best.get('value'),
            'href': resolved_href,
            'kind': 'click',
            'category': category,
        })
    seen = set()
    unique = []
    for action in actions:
        key = (action.get('text'), action.get('locator_strategy'), action.get('locator_value'), action.get('href'))
        if key not in seen:
            seen.add(key)
            unique.append(action)
    return unique[:100]


def classify_graph_action(text, kind=''):
    normalized = normalize_keyword_text(text or '')
    if text and DANGEROUS_TEXT_RE.search(text):
        return 'destructive'
    if any(keyword in normalized for keyword in ('delete', 'remove', 'logout', 'submit', 'save', 'confirm', 'reset')):
        return 'destructive'
    if any(keyword in normalized for keyword in ('detail', 'edit', 'add', 'new', 'open', 'next', 'view')):
        return 'form_action'
    if NAVIGATION_TEXT_RE.search(text or '') or str(kind).lower() in {'link', 'tab', 'menuitem'}:
        return 'navigation'
    return 'unknown'


def action_fingerprint(source_key, action):
    return '|'.join([
        str(source_key or ''),
        str(action.get('kind') or ''),
        str(action.get('locator_strategy') or ''),
        str(action.get('locator_value') or ''),
        str(action.get('href') or ''),
    ])


def build_replay_and_click_js(action_path, action):
    actions = list(action_path or []) + [action]
    return f"""
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const visible = (el) => {{
  if (!el) return false;
  const style = getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && !el.disabled;
}};
const cssEscape = (value) => window.CSS && CSS.escape ? CSS.escape(value) : String(value).replace(/["\\\\]/g, '\\\\$&');
const xpathAll = (value) => {{
  const result = [];
  try {{
    const iterator = document.evaluate(value, document, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);
    let node = iterator.iterateNext();
    while (node) {{
      if (node.nodeType === 1) result.push(node);
      node = iterator.iterateNext();
    }}
  }} catch (e) {{}}
  return result;
}};
const textOf = (el) => (el?.innerText || el?.value || el?.getAttribute?.('aria-label') || el?.getAttribute?.('title') || '').trim().replace(/\\s+/g, ' ');
const queryAction = (action) => {{
  const strategy = String(action.locator_strategy || '').toLowerCase();
  const value = String(action.locator_value || '');
  const text = String(action.text || action.name || '').trim();
  let elements = [];
  try {{
    if (strategy === 'id') elements = Array.from(document.querySelectorAll('#' + cssEscape(value)));
    else if (strategy === 'name') elements = Array.from(document.querySelectorAll('[name="' + cssEscape(value) + '"]'));
    else if (strategy === 'placeholder') elements = Array.from(document.querySelectorAll('input,textarea')).filter((el) => el.getAttribute('placeholder') === value);
    else if (strategy === 'test-id') elements = Array.from(document.querySelectorAll('[data-testid="' + cssEscape(value) + '"]'));
    else if (strategy === 'css') elements = Array.from(document.querySelectorAll(value));
    else if (strategy === 'xpath') elements = xpathAll(value);
    else if (strategy === 'text') elements = Array.from(document.querySelectorAll('a,button,[role="button"],[role="link"],[role="menuitem"],[role="tab"],[role="treeitem"],[role="option"]')).filter((el) => textOf(el) === value);
  }} catch (e) {{}}
  if (!elements.length && text) {{
    elements = Array.from(document.querySelectorAll('a,button,[role="button"],[role="link"],[role="menuitem"],[role="tab"],[role="treeitem"],[role="option"]'))
      .filter((el) => textOf(el) === text || textOf(el).includes(text));
  }}
  return elements.find(visible) || elements[0] || null;
}};
const waitAfterAction = async (beforeUrl) => {{
  for (let i = 0; i < 20; i += 1) {{
    await sleep(150);
    if (location.href !== beforeUrl) break;
  }}
  await sleep(900);
}};
for (const action of {json.dumps(actions, ensure_ascii=True)}) {{
  const beforeUrl = location.href;
  if (action.href) {{
    location.href = action.href;
    await waitAfterAction(beforeUrl);
    continue;
  }}
  const target = queryAction(action);
  if (!target) {{
    await sleep(300);
    continue;
  }}
  target.scrollIntoView({{ block: 'center', inline: 'center' }});
  target.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }}));
  target.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window }}));
  target.click();
  await waitAfterAction(beforeUrl);
}}
return {{ snapshot: await ({page_extract_script()})() }};
"""


def perform_login_if_needed(page, options):
    if not options.username and not options.password:
        page.goto(options.start_url, wait_until='domcontentloaded', timeout=options.timeout_ms)
        try:
            page.wait_for_load_state('networkidle', timeout=8000)
        except PlaywrightTimeoutError:
            pass
        return page.url

    page.goto(options.login_url or options.start_url, wait_until='domcontentloaded', timeout=options.timeout_ms)
    username_selector = options.username_selector or find_first_existing_selector(
        page,
        [
            'input[name="username"]',
            'input[name="userName"]',
            'input[name="account"]',
            'input[type="text"]',
            'input[placeholder*="账号"]',
            'input[placeholder*="用户"]',
            'input[placeholder*="邮箱"]',
            'input[placeholder*="username" i]',
        ],
    )
    password_selector = options.password_selector or find_first_existing_selector(
        page,
        [
            'input[type="password"]',
            'input[name="password"]',
            'input[placeholder*="密码"]',
            'input[placeholder*="password" i]',
        ],
    )
    if username_selector and options.username:
        page.locator(username_selector).first.fill(options.username)
    if password_selector and options.password:
        page.locator(password_selector).first.fill(options.password)

    submit_selector = options.submit_selector or find_first_existing_selector(
        page,
        [
            'button[type="submit"]',
            'button:has-text("登录")',
            'button:has-text("登 录")',
            'button:has-text("Login")',
            '[role="button"]:has-text("登录")',
        ],
    )
    if submit_selector:
        page.locator(submit_selector).first.click()
    elif password_selector:
        page.locator(password_selector).first.press('Enter')

    try:
        page.wait_for_load_state('networkidle', timeout=8000)
    except PlaywrightTimeoutError:
        pass
    try:
        page.wait_for_timeout(800)
    except Exception:
        pass
    return page.url


def find_first_existing_selector(page, selectors):
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return selector
        except Exception:
            continue
    return ''


def perform_login_if_needed(page, options):
    if not options.username and not options.password:
        page.goto(options.start_url, wait_until='domcontentloaded', timeout=options.timeout_ms)
        try:
            page.wait_for_load_state('networkidle', timeout=8000)
        except PlaywrightTimeoutError:
            pass
        return page.url

    page.goto(options.login_url or options.start_url, wait_until='domcontentloaded', timeout=options.timeout_ms)
    username_selector = options.username_selector or find_first_existing_selector(
        page,
        [
            'input[name="username"]',
            'input[name="user"]',
            'input[name="userName"]',
            'input[name="account"]',
            'input[name="loginName"]',
            'input[name="phone"]',
            'input[name="mobile"]',
            'input[autocomplete="username"]',
            'input[placeholder*="账号"]',
            'input[placeholder*="用户"]',
            'input[placeholder*="用户名"]',
            'input[placeholder*="手机"]',
            'input[placeholder*="邮箱"]',
            'input[placeholder*="请输入账号"]',
            'input[placeholder*="username" i]',
            'input[placeholder*="account" i]',
            'input[placeholder*="user" i]',
            'input[placeholder*="email" i]',
            'input[type="text"]',
            'input:not([type])',
        ],
    )
    password_selector = options.password_selector or find_first_existing_selector(
        page,
        [
            'input[type="password"]',
            'input[name="password"]',
            'input[autocomplete="current-password"]',
            'input[placeholder*="密码"]',
            'input[placeholder*="请输入密码"]',
            'input[placeholder*="password" i]',
        ],
    )
    if not username_selector:
        username_selector = find_visible_input_near_password(page)
    if not password_selector:
        raise ValueError('自动登录失败：未找到密码输入框，请填写密码输入框 CSS 选择器')
    if options.username and not username_selector:
        raise ValueError('自动登录失败：未找到账号输入框，请填写账号输入框 CSS 选择器')

    logger.info('Page graph login selectors: username=%s password=%s', username_selector, password_selector)
    if username_selector and options.username:
        page.locator(username_selector).first.fill(options.username)
    if password_selector and options.password:
        page.locator(password_selector).first.fill(options.password)

    before_url = normalize_url(page.url)
    clicked = click_login_submit(page, options.submit_selector)
    if not clicked:
        page.locator(password_selector).first.press('Enter')

    wait_for_post_login(page, before_url)
    after_url = normalize_url(page.url)
    logger.info('Page graph login navigation: before=%s after=%s clicked=%s', before_url, after_url, clicked)
    if is_login_url(after_url) or after_url == before_url:
        try:
            if page.locator('input[type="password"]').count() > 0:
                raise ValueError('自动登录失败：提交后仍停留在登录页，请检查账号密码或填写登录按钮 CSS 选择器')
        except ValueError:
            raise
        except Exception:
            pass
    return page.url


def is_login_url(url):
    parsed = urlparse(normalize_url(url))
    value = f'{parsed.path}#{parsed.fragment}'.lower()
    return any(keyword in value for keyword in ('login', 'signin', 'sign-in', 'auth'))


def find_visible_input_near_password(page):
    return find_first_existing_selector(
        page,
        [
            'input:not([type="password"]):not([type="hidden"]):not([disabled])',
            '.login input:not([type="password"]):not([type="hidden"])',
            '.login-form input:not([type="password"]):not([type="hidden"])',
            'form input:not([type="password"]):not([type="hidden"])',
        ],
    )


def click_login_submit(page, explicit_selector=''):
    selectors = [explicit_selector] if explicit_selector else []
    selectors.extend([
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("登录")',
        'button:has-text("登陆")',
        'button:has-text("立即登录")',
        'button:has-text("Sign in")',
        'button:has-text("Sign In")',
        'button:has-text("Login")',
        '[role="button"]:has-text("登录")',
        '[role="button"]:has-text("登陆")',
        '[role="button"]:has-text("Login")',
        '.login button',
        '.login-form button',
        'form button',
        'button',
    ])
    for selector in selectors:
        if not selector:
            continue
        try:
            locator = page.locator(selector)
            count = locator.count()
            for index in range(min(count, 8)):
                item = locator.nth(index)
                if item.is_visible() and item.is_enabled():
                    item.click(timeout=5000)
                    return True
        except Exception:
            continue
    return False


def wait_for_post_login(page, before_url):
    try:
        page.wait_for_url(lambda url: normalize_url(url) != before_url, timeout=10000)
    except Exception:
        pass
    try:
        page.wait_for_load_state('networkidle', timeout=10000)
    except PlaywrightTimeoutError:
        pass
    try:
        page.wait_for_timeout(1200)
    except Exception:
        pass


def upsert_page_node(graph, project, snapshot):
    url = normalize_url(snapshot.get('url') or '')
    route_key = snapshot.get('state_key') or state_key_for_snapshot(snapshot)
    title = compact_text(snapshot.get('title'), 300)
    page_text = compact_text(snapshot.get('body_text'), 5000)
    node, _ = UIPageNode.objects.update_or_create(
        graph=graph,
        route_key=route_key,
        defaults={
            'project': project,
            'url': url,
            'path': route_key_for_url(url) or urlparse(url).path or '/',
            'title': title,
            'page_text': page_text,
            'keywords': extract_keywords(title, page_text, route_key),
            'metadata': {
                'captured_url': snapshot.get('url'),
                'state_key': route_key,
                'depth': snapshot.get('depth', 0),
            },
        },
    )
    return node


def build_page_element_payload(node, page, item):
    locators = build_locator_candidates(item)
    best, checked = choose_best_locator(page, locators)
    if not best.get('value'):
        return None

    attrs = item.get('attributes') or {}
    text = compact_text(item.get('text'), 200)
    name = (
        text
        or attrs.get('aria-label')
        or attrs.get('placeholder')
        or attrs.get('title')
        or attrs.get('name')
        or f'{item.get("tag") or "element"}元素'
    )[:240]
    element_type = infer_element_type(item.get('tag'), attrs.get('type'), item.get('role'), text)
    signature = dom_signature(item)
    action_keywords = extract_keywords(name, text, node.title, node.path)
    backup = [
        {'strategy': candidate.get('strategy'), 'value': candidate.get('value'), 'match_count': candidate.get('match_count')}
        for candidate in checked
        if candidate.get('value') != best.get('value')
    ][:5]

    return {
        'name': name,
        'role': item.get('role') or '',
        'element_type': element_type,
        'text': text,
        'locator_strategy': locator_name_for_strategy(best.get('strategy')),
        'locator_value': best.get('value'),
        'backup_locators': backup,
        'is_unique': bool(best.get('is_unique')),
        'is_stable': bool(best.get('is_unique')) and score_locator(best) >= 60,
        'action_keywords': action_keywords,
        'attributes': attrs,
        'bounds': item.get('bounds') or {},
        'dom_signature': signature,
    }


def build_page_element_payload_from_snapshot(node, item):
    locators = build_locator_candidates(item)
    checked = sorted(locators, key=score_locator, reverse=True)
    best = checked[0] if checked else None
    if not best or not best.get('value'):
        return None

    attrs = item.get('attributes') or {}
    text = compact_text(item.get('text'), 200)
    name = (
        text
        or attrs.get('aria-label')
        or attrs.get('placeholder')
        or attrs.get('title')
        or attrs.get('name')
        or f'{item.get("tag") or "element"}元素'
    )[:240]
    element_type = infer_element_type(item.get('tag'), attrs.get('type'), item.get('role'), text)
    signature = dom_signature(item)
    action_keywords = extract_keywords(name, text, node.title, node.path)
    backup = [
        {'strategy': candidate.get('strategy'), 'value': candidate.get('value'), 'match_count': candidate.get('match_count', 0)}
        for candidate in checked
        if candidate.get('value') != best.get('value')
    ][:5]
    stable_score = score_locator(best)

    return {
        'name': name,
        'role': item.get('role') or '',
        'element_type': element_type,
        'text': text,
        'locator_strategy': locator_name_for_strategy(best.get('strategy')),
        'locator_value': best.get('value'),
        'backup_locators': backup,
        'is_unique': stable_score >= 70,
        'is_stable': stable_score >= 70,
        'action_keywords': action_keywords,
        'attributes': attrs,
        'bounds': item.get('bounds') or {},
        'dom_signature': signature,
    }


def persist_page_element(graph, project, node, payload, sync_element):
    graph_element = UIPageElement.objects.create(
        graph=graph,
        page_node=node,
        project=project,
        name=payload['name'],
        role=payload['role'],
        element_type=payload['element_type'],
        text=payload['text'],
        locator_strategy=payload['locator_strategy'],
        locator_value=payload['locator_value'],
        backup_locators=payload['backup_locators'],
        is_unique=payload['is_unique'],
        is_stable=payload['is_stable'],
        action_keywords=payload['action_keywords'],
        attributes=payload['attributes'],
        bounds=payload['bounds'],
        dom_signature=payload['dom_signature'],
    )

    synced = False
    if sync_element and graph_element.is_unique:
        element = sync_graph_element_to_element_library(project, node, graph_element)
        graph_element.element = element
        graph_element.save(update_fields=['element', 'updated_at'])
        synced = True

    return graph_element, synced


def sync_graph_element_to_element_library(project, node, graph_element):
    strategy = get_locator_strategy(graph_element.locator_strategy)
    group = ensure_graph_element_group(project, node)
    defaults = {
        'description': f'页面图谱自动同步: {node.title or node.path}',
        'element_type': graph_element.element_type,
        'locator_strategy': strategy,
        'locator_value': graph_element.locator_value,
        'backup_locators': graph_element.backup_locators,
        'page': node.title or node.path,
        'component_name': node.path or '',
        'group': group,
        'is_unique': graph_element.is_unique,
        'is_visible': True,
        'is_enabled': True,
        'validation_status': 'VALID' if graph_element.is_unique else 'UNKNOWN',
        'last_validated': timezone.now() if graph_element.is_unique else None,
        'validation_message': 'Synced from page graph crawler',
    }
    existing = Element.objects.filter(
        project=project,
        page=defaults['page'],
        name=graph_element.name,
    ).first()
    if existing:
        for key, value in defaults.items():
            setattr(existing, key, value)
        existing.save()
        return existing
    return Element.objects.create(project=project, name=graph_element.name, **defaults)


def ensure_graph_element_group(project, node):
    parent, _ = ElementGroup.objects.get_or_create(
        project=project,
        name='页面图谱自动同步',
        parent_group=None,
        defaults={'description': 'Elements synced from UI page graph crawler', 'order': 9000},
    )
    child_name = (node.title or node.path or '未命名页面')[:200]
    child, _ = ElementGroup.objects.get_or_create(
        project=project,
        name=child_name,
        parent_group=parent,
        defaults={'description': node.url, 'order': 0},
    )
    return child


def discover_navigation_links(snapshot, current_url, base_url):
    links = []
    for link in snapshot.get('links') or []:
        href = normalize_url(urljoin(current_url, link.get('href') or ''))
        if not href or not same_origin(href, base_url):
            continue
        if href == normalize_url(current_url):
            continue
        links.append({'href': href, 'text': link.get('text') or ''})
    return links[:80]


def discover_safe_navigation_elements(snapshot, current_url):
    candidates = []
    for item in snapshot.get('elements') or []:
        text = compact_text(item.get('text') or (item.get('attributes') or {}).get('aria-label'), 120)
        if not text or not is_stable_attribute_value(text) or DANGEROUS_TEXT_RE.search(text):
            continue
        role = str(item.get('role') or '').lower()
        tag = str(item.get('tag') or '').lower()
        is_link_like = tag == 'a' or role in {'link', 'menuitem', 'tab'}
        is_button_like = tag == 'button' or role == 'button'
        if not is_link_like and not is_button_like:
            continue
        if is_button_like and not NAVIGATION_TEXT_RE.search(text):
            continue
        candidates_data = build_locator_candidates(item)
        best = sorted(candidates_data, key=score_locator, reverse=True)[0] if candidates_data else None
        if not best:
            continue
        payload = dict(item)
        payload['name'] = text
        payload['locator_strategy'] = locator_name_for_strategy(best.get('strategy'))
        payload['locator_value'] = best.get('value')
        payload['current_url'] = current_url
        candidates.append(payload)
    return candidates[:20]


def click_navigation_candidate(page, item, current_url, base_url, timeout_ms):
    strategy = str(item.get('locator_strategy') or '').lower()
    value = item.get('locator_value') or ''
    if not value:
        return ''
    try:
        page.goto(current_url, wait_until='domcontentloaded', timeout=timeout_ms)
        if strategy == 'xpath':
            locator = page.locator(f'xpath={value}').first
        elif strategy == 'text':
            locator = page.get_by_text(value, exact=True).first
        else:
            locator = page.locator(value).first
        before = normalize_url(page.url)
        locator.click(timeout=3000)
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except PlaywrightTimeoutError:
            pass
        after = normalize_url(page.url)
        if after and after != before and same_origin(after, base_url):
            return after
    except Exception:
        return ''
    return ''


def create_page_edge(graph, project, source, target, payload):
    if source.id == target.id:
        return None
    existing = UIPageEdge.objects.filter(
        graph=graph,
        source=source,
        target=target,
        trigger_text=payload.get('trigger_text') or '',
    ).first()
    if existing:
        return existing
    trigger_element = None
    locator_value = payload.get('locator_value') or ''
    if locator_value:
        trigger_element = UIPageElement.objects.filter(
            graph=graph,
            page_node=source,
            locator_value=locator_value,
        ).first()
    return UIPageEdge.objects.create(
        graph=graph,
        project=project,
        source=source,
        target=target,
        trigger_element=trigger_element,
        action_type='click',
        trigger_text=payload.get('trigger_text') or '',
        locator_strategy=payload.get('locator_strategy') or '',
        locator_value=locator_value,
        keywords=payload.get('keywords') or [],
        metadata=payload.get('metadata') or {},
    )


def latest_completed_graph(project):
    return UIPageGraph.objects.filter(project=project, status='completed').order_by('-completed_at', '-created_at').first()


def latest_generation_graph(project):
    completed = latest_completed_graph(project)
    if completed and UIPageNode.objects.filter(graph=completed).exists():
        return completed
    return (
        UIPageGraph.objects.filter(project=project, status__in=['running', 'timeout', 'cancelled', 'failed'])
        .annotate(node_total=models.Count('nodes'), edge_total=models.Count('edges'))
        .filter(node_total__gt=0)
        .order_by('-updated_at', '-created_at')
        .first()
    )


def build_page_graph_context(project, source_text='', limit=120):
    graph = latest_generation_graph(project)
    if not graph:
        return ''

    matches = search_graph(project, source_text, graph=graph, limit=limit)
    lines = [
        'Graph usage: when a matching page, path, or element is listed below, generate navigation and element steps from this graph first; copy locator_strategy and locator_value exactly; do not invent another locator unless no graph match exists.',
        f'图谱: {graph.name} pages={graph.summary.get("pages", 0)} elements={graph.summary.get("elements", 0)} edges={graph.summary.get("edges", 0)}',
        '要求: 生成步骤时优先复用下列图谱路径和唯一元素定位器；locator_value 必须原样使用，不要改写动态 XPath。',
    ]
    for item in matches[:limit]:
        if item['kind'] == 'page':
            lines.append(f'- page:{item["title"] or item["path"]} url:{item["url"]} keywords:{",".join(item["keywords"][:8])}')
        elif item['kind'] == 'edge':
            lines.append(
                f'- path:{item["source"]} --点击[{item["trigger_text"]}]--> {item["target"]} '
                f'locator:{item["locator_strategy"]}={item["locator_value"]}'
            )
        else:
            lines.append(
                f'- element page:{item["page"]} name:{item["name"]} type:{item["element_type"]} '
                f'unique:{item["is_unique"]} stable:{item["is_stable"]} '
                f'locator:{item["locator_strategy"]}={item["locator_value"]}'
            )
    return '\n'.join(lines)


def build_page_graph_route_plan(project, source_text='', graph=None, max_paths=5, max_depth=8, target_limit=8):
    graph = graph or latest_generation_graph(project)
    if not graph:
        return {}
    target_nodes = find_graph_target_nodes(project, source_text, graph, limit=target_limit)
    if not target_nodes:
        return {
            'graph_id': graph.id,
            'graph_name': graph.name,
            'graph_status': graph.status,
            'paths': [],
            'target_elements': [],
        }
    entry_nodes = find_graph_entry_nodes(graph, start_url=graph.start_url, limit=5)
    paths = find_navigation_paths(graph, entry_nodes, target_nodes, max_depth=max_depth, max_paths=max_paths)
    target_node_ids = [path.get('target_node_id') for path in paths if path.get('target_node_id')]
    if not target_node_ids:
        target_node_ids = [item['node'].id for item in target_nodes[:max_paths]]
    target_elements = collect_target_page_elements(graph, source_text, target_node_ids, limit=max_paths * 8)
    return {
        'graph_id': graph.id,
        'graph_name': graph.name,
        'graph_status': graph.status,
        'graph_summary': graph.summary or {},
        'paths': paths,
        'target_elements': target_elements,
    }


def build_page_graph_route_context(project, source_text='', graph=None, max_paths=5, max_depth=8):
    return format_page_graph_route_context(
        build_page_graph_route_plan(
            project,
            source_text,
            graph=graph,
            max_paths=max_paths,
            max_depth=max_depth,
        )
    )


def find_graph_entry_nodes(graph, start_url='', limit=5):
    normalized_start = normalize_url(start_url or graph.start_url or '')
    start_route = route_key_for_url(normalized_start)
    nodes = list(
        UIPageNode.objects.filter(graph=graph)
        .annotate(outgoing_count=models.Count('outgoing_edges'))
        .order_by('created_at')[:1000]
    )
    scored = []
    for node in nodes:
        route = node.route_key or route_key_for_url(node.url)
        text = normalize_keyword_text(' '.join([node.title, node.path, route, node.url]))
        score = 0
        if normalized_start and normalize_url(node.url) == normalized_start:
            score += 100
        if start_route and route == start_route:
            score += 80
        if route in {'/', '', '#/', '/#/', '#/'} or any(keyword in text for keyword in ('home', 'homepage', 'dashboard', 'index', '首页', '主页')):
            score += 35
        if int((node.metadata or {}).get('depth') or 0) == 0:
            score += 20
        score += min(int(getattr(node, 'outgoing_count', 0) or 0), 20)
        scored.append((score, node.id, node))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:limit]] or nodes[:limit]


def find_graph_target_nodes(project, query, graph, limit=8):
    tokens = extract_keywords(query, limit=40)
    normalized_query = normalize_keyword_text(query)
    if not normalized_query and not tokens:
        return []

    best = {}

    def add_candidate(node, score, reason, matched_text=''):
        if not node or score <= 0:
            return
        current = best.get(node.id)
        payload = {
            'node': node,
            'score': score,
            'reason': reason,
            'matched_text': compact_text(matched_text, 180),
        }
        if not current or score > current['score']:
            best[node.id] = payload

    for node in UIPageNode.objects.filter(graph=graph).order_by('-updated_at')[:1200]:
        text = ' '.join([node.title, node.path, node.route_key, node.page_text, ' '.join(node.keywords or [])])
        score = score_text_match(normalize_keyword_text(text), normalized_query, tokens)
        add_candidate(node, score, 'page', text)

    elements = UIPageElement.objects.filter(graph=graph).select_related('page_node').order_by('-is_unique', '-is_stable')[:2500]
    for element in elements:
        text = ' '.join([
            element.name,
            element.text,
            element.element_type,
            element.page_node.title,
            element.page_node.path,
            ' '.join(element.action_keywords or []),
        ])
        score = score_text_match(normalize_keyword_text(text), normalized_query, tokens)
        if score > 0:
            score += 4
            if element.is_unique:
                score += 3
            if element.is_stable:
                score += 2
        add_candidate(element.page_node, score, f'element:{element.name}', text)

    edges = UIPageEdge.objects.filter(graph=graph).select_related('source', 'target')[:1500]
    for edge in edges:
        text = ' '.join([
            edge.trigger_text,
            edge.source.title,
            edge.source.path,
            edge.target.title,
            edge.target.path,
            ' '.join(edge.keywords or []),
        ])
        score = score_text_match(normalize_keyword_text(text), normalized_query, tokens)
        if score > 0:
            score += 2
        add_candidate(edge.target, score, f'edge:{edge.trigger_text}', text)

    return sorted(best.values(), key=lambda item: (-item['score'], item['node'].id))[:limit]


def find_navigation_paths(graph, entry_nodes, target_nodes, max_depth=8, max_paths=5):
    target_by_id = {item['node'].id: item for item in target_nodes}
    if not entry_nodes or not target_by_id:
        return []
    edges = list(
        UIPageEdge.objects.filter(graph=graph)
        .select_related('source', 'target')
        .order_by('source_id', 'target_id', 'trigger_text')[:5000]
    )
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge.source_id, []).append(edge)
    for source_id, source_edges in adjacency.items():
        adjacency[source_id] = sorted(source_edges, key=lambda edge: (0 if edge.locator_value else 1, edge.trigger_text or '', edge.id))

    paths = []
    seen_path_keys = set()
    for entry in entry_nodes:
        queue = deque([(entry, [])])
        visited_depth = {entry.id: 0}
        while queue and len(paths) < max_paths:
            node, path_edges = queue.popleft()
            depth = len(path_edges)
            if node.id in target_by_id:
                path_key = tuple(edge.id for edge in path_edges) or (node.id,)
                if path_key not in seen_path_keys:
                    seen_path_keys.add(path_key)
                    target = target_by_id[node.id]
                    paths.append(format_navigation_path(entry, target, path_edges))
                if len(paths) >= max_paths:
                    break
            if depth >= max_depth:
                continue
            for edge in adjacency.get(node.id, [])[:120]:
                next_depth = depth + 1
                if visited_depth.get(edge.target_id, max_depth + 1) <= next_depth:
                    continue
                visited_depth[edge.target_id] = next_depth
                queue.append((edge.target, path_edges + [edge]))
    if not paths:
        paths = find_partial_navigation_paths(graph, target_nodes, edges, max_depth=max_depth, max_paths=max_paths)
    return sorted(paths, key=lambda item: (-item.get('score', 0), len(item.get('steps') or []), item.get('target_page') or ''))[:max_paths]


def find_partial_navigation_paths(graph, target_nodes, edges, max_depth=8, max_paths=5):
    incoming = {}
    node_by_id = {}
    for edge in edges:
        incoming.setdefault(edge.target_id, []).append(edge)
        node_by_id[edge.source_id] = edge.source
        node_by_id[edge.target_id] = edge.target
    paths = []
    seen_path_keys = set()
    for target_candidate in target_nodes:
        target_node = target_candidate['node']
        queue = deque([(target_node, [])])
        visited = {target_node.id}
        while queue and len(paths) < max_paths:
            node, reversed_edges = queue.popleft()
            if reversed_edges:
                path_edges = list(reversed(reversed_edges))
                path_key = tuple(edge.id for edge in path_edges)
                if path_key not in seen_path_keys:
                    seen_path_keys.add(path_key)
                    entry_node = path_edges[0].source
                    path = format_navigation_path(entry_node, target_candidate, path_edges)
                    path['path_scope'] = 'partial'
                    paths.append(path)
                    break
            if len(reversed_edges) >= max_depth:
                continue
            for edge in incoming.get(node.id, [])[:120]:
                if edge.source_id in visited:
                    continue
                visited.add(edge.source_id)
                queue.append((edge.source, reversed_edges + [edge]))
    return paths[:max_paths]


def format_navigation_path(entry_node, target_candidate, path_edges):
    target_node = target_candidate['node']
    steps = []
    for index, edge in enumerate(path_edges, start=1):
        steps.append({
            'step': index,
            'source_page': edge.source.title or edge.source.path or edge.source.url,
            'target_page': edge.target.title or edge.target.path or edge.target.url,
            'action_type': edge.action_type or 'click',
            'trigger_text': edge.trigger_text or '',
            'locator_strategy': edge.locator_strategy or '',
            'locator_value': edge.locator_value or '',
        })
    return {
        'entry_node_id': entry_node.id,
        'entry_page': entry_node.title or entry_node.path or entry_node.url,
        'target_node_id': target_node.id,
        'target_page': target_node.title or target_node.path or target_node.url,
        'target_url': target_node.url,
        'target_reason': target_candidate.get('reason') or '',
        'score': max(0, int(target_candidate.get('score') or 0) - len(steps)),
        'steps': steps,
    }


def collect_target_page_elements(graph, query, target_node_ids, limit=40):
    if not target_node_ids:
        return []
    tokens = extract_keywords(query, limit=40)
    normalized_query = normalize_keyword_text(query)
    elements = []
    queryset = (
        UIPageElement.objects.filter(graph=graph, page_node_id__in=target_node_ids)
        .select_related('page_node')
        .order_by('-is_unique', '-is_stable', 'name')[:800]
    )
    seen = set()
    for element in queryset:
        text = normalize_keyword_text(' '.join([
            element.name,
            element.text,
            element.element_type,
            element.page_node.title,
            element.page_node.path,
            ' '.join(element.action_keywords or []),
        ]))
        score = score_text_match(text, normalized_query, tokens)
        if element.is_unique:
            score += 3
        if element.is_stable:
            score += 2
        key = (element.page_node_id, element.locator_strategy, element.locator_value)
        if key in seen:
            continue
        seen.add(key)
        if score <= 1 and not (element.is_unique and element.is_stable):
            continue
        elements.append({
            'score': score,
            'page': element.page_node.title or element.page_node.path,
            'name': element.name,
            'element_type': element.element_type,
            'locator_strategy': element.locator_strategy,
            'locator_value': element.locator_value,
            'is_unique': element.is_unique,
            'is_stable': element.is_stable,
        })
    return sorted(elements, key=lambda item: (-item['score'], item['page'], item['name']))[:limit]


def format_page_graph_route_context(plan):
    if not plan:
        return ''
    lines = [
        '【页面图谱路径规划 - 强约束】',
        f'图谱: {plan.get("graph_name")} id={plan.get("graph_id")} status={plan.get("graph_status")}',
        '使用规则: 如果推荐路径命中当前用例目标，必须先按推荐路径顺序生成导航步骤；每个导航步骤必须原样复制 locator_strategy 和 locator_value；到达目标页面后，优先复用目标页面可用元素。',
    ]
    paths = plan.get('paths') or []
    if not paths:
        lines.append('未找到从入口页到目标页的完整推荐路径；可以继续使用下方目标页面元素和普通图谱上下文，但必须避免编造定位器。')
    for index, path in enumerate(paths[:5], start=1):
        lines.append(
            f'推荐路径 {index}: scope={path.get("path_scope") or "full"} entry={path.get("entry_page")} -> target={path.get("target_page")} '
            f'score={path.get("score")} reason={path.get("target_reason")}'
        )
        steps = path.get('steps') or []
        if not steps:
            lines.append('  0. 当前入口已是目标页面，无需额外导航。')
        for step in steps:
            lines.append(
                f'  {step.get("step")}. 在[{step.get("source_page")}] {step.get("action_type") or "click"} '
                f'[{step.get("trigger_text") or step.get("target_page")}] -> [{step.get("target_page")}] '
                f'locator:{step.get("locator_strategy")}={step.get("locator_value")}'
            )
    target_elements = plan.get('target_elements') or []
    if target_elements:
        lines.append('目标页面可用元素:')
        for element in target_elements[:40]:
            lines.append(
                f'- page:{element.get("page")} element:{element.get("name")} type:{element.get("element_type")} '
                f'unique:{element.get("is_unique")} stable:{element.get("is_stable")} '
                f'locator:{element.get("locator_strategy")}={element.get("locator_value")}'
            )
    return '\n'.join(lines)


def search_graph(project, query, graph=None, limit=80):
    graph = graph or latest_generation_graph(project)
    if not graph:
        return []
    tokens = extract_keywords(query, limit=40)
    normalized_query = normalize_keyword_text(query)

    results = []
    for node in UIPageNode.objects.filter(graph=graph).order_by('path')[:500]:
        text = normalize_keyword_text(' '.join([node.title, node.path, node.page_text, ' '.join(node.keywords or [])]))
        score = score_text_match(text, normalized_query, tokens)
        if score > 0 or not normalized_query:
            results.append({
                'kind': 'page',
                'score': score,
                'id': node.id,
                'title': node.title,
                'path': node.path,
                'url': node.url,
                'keywords': node.keywords or [],
            })

    for edge in UIPageEdge.objects.filter(graph=graph).select_related('source', 'target')[:1000]:
        text = normalize_keyword_text(' '.join([edge.trigger_text, edge.source.title, edge.target.title, ' '.join(edge.keywords or [])]))
        score = score_text_match(text, normalized_query, tokens) + 1
        if score > 1 or not normalized_query:
            results.append({
                'kind': 'edge',
                'score': score,
                'id': edge.id,
                'source': edge.source.title or edge.source.path,
                'target': edge.target.title or edge.target.path,
                'trigger_text': edge.trigger_text,
                'locator_strategy': edge.locator_strategy,
                'locator_value': edge.locator_value,
                'keywords': edge.keywords or [],
            })

    for element in UIPageElement.objects.filter(graph=graph).select_related('page_node').order_by('-is_unique', '-is_stable')[:2000]:
        text = normalize_keyword_text(' '.join([element.name, element.text, element.page_node.title, element.page_node.path, ' '.join(element.action_keywords or [])]))
        score = score_text_match(text, normalized_query, tokens) + (4 if element.is_unique else 0) + (2 if element.is_stable else 0)
        if score > 2 or not normalized_query:
            results.append({
                'kind': 'element',
                'score': score,
                'id': element.id,
                'element_id': element.element_id,
                'page': element.page_node.title or element.page_node.path,
                'name': element.name,
                'element_type': element.element_type,
                'locator_strategy': element.locator_strategy,
                'locator_value': element.locator_value,
                'is_unique': element.is_unique,
                'is_stable': element.is_stable,
                'keywords': element.action_keywords or [],
            })

    return sorted(results, key=lambda item: (-item['score'], item['kind']))[:limit]


def score_text_match(text, normalized_query, tokens):
    if not normalized_query:
        return 1
    score = 0
    if normalized_query and normalized_query in text:
        score += 10
    for token in tokens:
        normalized = normalize_keyword_text(token)
        if normalized and normalized in text:
            score += 2 + min(text.count(normalized), 3)
    return score
