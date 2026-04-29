import time
import uuid
from threading import Event, RLock


LOCAL_SCROLL_COORDINATE_PICKER_SESSION_TTL = 1800
LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS = {}
LOCAL_SCROLL_COORDINATE_PICKER_LOCK = RLock()


def _normalize_browser_name(browser):
    return {
        'chrome': 'chromium',
        'edge': 'chromium',
        'firefox': 'firefox',
        'safari': 'webkit',
        'chromium': 'chromium',
        'webkit': 'webkit',
    }.get(str(browser or 'chrome').lower(), 'chromium')


def cleanup_local_scroll_coordinate_picker_sessions(user_id=None, runner_id=None):
    now = time.time()
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        for session_id, session in list(LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.items()):
            if user_id is not None and session.get('user_id') != user_id:
                continue
            if runner_id is not None and session.get('runner_id') != runner_id:
                continue
            last_used_at = session.get('last_used_at', session.get('created_at', now))
            if now - last_used_at <= LOCAL_SCROLL_COORDINATE_PICKER_SESSION_TTL:
                continue
            LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.pop(session_id, None)


def close_user_local_scroll_coordinate_picker_sessions(user_id):
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        for session_id, session in list(LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.items()):
            if session.get('user_id') != user_id:
                continue
            session['state'] = 'closed'
            session['closed_at'] = time.time()
            session.get('ready_event', Event()).set()
            command = session.get('command')
            if command:
                command.get('event', Event()).set()
            LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.pop(session_id, None)


def create_local_scroll_coordinate_picker_session(user_id, runner_id, base_url, browser='chrome', picker_element_data=None):
    cleanup_local_scroll_coordinate_picker_sessions(user_id=user_id)
    close_user_local_scroll_coordinate_picker_sessions(user_id)

    session_id = uuid.uuid4().hex
    session = {
        'session_id': session_id,
        'user_id': user_id,
        'runner_id': runner_id,
        'base_url': base_url,
        'browser_name': _normalize_browser_name(browser),
        'picker_element_data': picker_element_data or None,
        'created_at': time.time(),
        'last_used_at': time.time(),
        'state': 'pending_start',
        'error': '',
        'ready_event': Event(),
        'command': None,
        'next_sequence': 1,
    }
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS[session_id] = session
    return session


def get_local_scroll_coordinate_picker_session(session_id, user_id, strict=True):
    cleanup_local_scroll_coordinate_picker_sessions(user_id=user_id)
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        session = LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.get(session_id)
        if session and session.get('user_id') == user_id:
            session['last_used_at'] = time.time()
            return session
    if strict:
        raise ValueError('坐标采集会话不存在或已过期，请重新打开后再试')
    return None


def wait_local_scroll_coordinate_picker_ready(session, timeout=45):
    if not session.get('ready_event').wait(timeout=timeout):
        raise TimeoutError('本地执行器启动坐标采集浏览器超时，请确认访客机执行器在线且空闲')

    state = session.get('state')
    if state != 'ready':
        raise RuntimeError(session.get('error') or '本地执行器启动坐标采集浏览器失败')

    session['last_used_at'] = time.time()
    return session


def request_local_scroll_coordinate_picker_select_page(session, page_index, timeout=20):
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        if session.get('state') != 'ready':
            raise RuntimeError(session.get('error') or '鍧愭爣閲囬泦娴忚鍣ㄥ皻鏈噯澶囧畬鎴愶紝璇烽噸鏂版墦寮€鍚庡啀璇?')

        command = session.get('command')
        if command and command.get('status') in {'pending', 'claimed'}:
            raise RuntimeError('涓婁竴鏉″潗鏍囪鍙栨寚浠ゅ皻鏈畬鎴愶紝璇风◢鍚庨噸璇?')

        next_sequence = session.get('next_sequence', 1)
        command = {
            'sequence': next_sequence,
            'action': 'select_page',
            'page_index': int(page_index),
            'status': 'pending',
            'payload': None,
            'error': '',
            'event': Event(),
            'created_at': time.time(),
        }
        session['command'] = command
        session['next_sequence'] = next_sequence + 1
        session['last_used_at'] = time.time()

    if not command['event'].wait(timeout=timeout):
        raise TimeoutError('切换坐标采集页面超时，请确认访客机本地浏览器仍然打开')

    if command.get('status') != 'completed':
        raise RuntimeError(command.get('error') or '切换坐标采集页面失败')

    session['last_used_at'] = time.time()
    return command.get('payload') or {}


def request_local_scroll_coordinate_picker_pages(session, timeout=20):
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        if session.get('state') != 'ready':
            raise RuntimeError(session.get('error') or '鍧愭爣閲囬泦娴忚鍣ㄥ皻鏈噯澶囧畬鎴愶紝璇烽噸鏂版墦寮€鍚庡啀璇?')

        command = session.get('command')
        if command and command.get('status') in {'pending', 'claimed'}:
            raise RuntimeError('涓婁竴鏉″潗鏍囪鍙栨寚浠ゅ皻鏈畬鎴愶紝璇风◢鍚庨噸璇?')

        next_sequence = session.get('next_sequence', 1)
        command = {
            'sequence': next_sequence,
            'action': 'list_pages',
            'status': 'pending',
            'payload': None,
            'error': '',
            'event': Event(),
            'created_at': time.time(),
        }
        session['command'] = command
        session['next_sequence'] = next_sequence + 1
        session['last_used_at'] = time.time()

    if not command['event'].wait(timeout=timeout):
        raise TimeoutError('读取坐标采集页面列表超时，请确认访客机本地浏览器仍然打开')

    if command.get('status') != 'completed':
        raise RuntimeError(command.get('error') or '读取坐标采集页面列表失败')

    session['last_used_at'] = time.time()
    return command.get('payload') or {}


def request_local_scroll_coordinate_picker_position(session, timeout=30, field='start'):
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        if session.get('state') != 'ready':
            raise RuntimeError(session.get('error') or '坐标采集浏览器尚未准备完成，请重新打开后再试')

        command = session.get('command')
        if command and command.get('status') in {'pending', 'claimed'}:
            raise RuntimeError('上一条坐标读取指令尚未完成，请稍后重试')

        next_sequence = session.get('next_sequence', 1)
        command = {
            'sequence': next_sequence,
            'action': 'capture_click',
            'field': str(field or 'start').strip() or 'start',
            'status': 'pending',
            'payload': None,
            'error': '',
            'event': Event(),
            'created_at': time.time(),
        }
        session['command'] = command
        session['next_sequence'] = next_sequence + 1
        session['last_used_at'] = time.time()

    if not command['event'].wait(timeout=timeout):
        raise TimeoutError('读取滚动坐标超时，请确认访客机本地浏览器仍然打开')

    if command.get('status') != 'completed':
        raise RuntimeError(command.get('error') or '读取滚动坐标失败')

    session['last_used_at'] = time.time()
    return command.get('payload') or {}


def close_local_scroll_coordinate_picker_session(session):
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        if session.get('state') in {'closed', 'closing'}:
            return

        if session.get('state') == 'pending_start':
            session['state'] = 'closed'
            session['closed_at'] = time.time()
            session.get('ready_event').set()
            return

        next_sequence = session.get('next_sequence', 1)
        command = {
            'sequence': next_sequence,
            'action': 'close',
            'status': 'pending',
            'payload': {'success': True},
            'error': '',
            'event': Event(),
            'created_at': time.time(),
        }
        session['command'] = command
        session['next_sequence'] = next_sequence + 1
        session['state'] = 'closing'
        session['last_used_at'] = time.time()

    command['event'].wait(timeout=10)
    session['state'] = 'closed'
    session['closed_at'] = time.time()


def remove_local_scroll_coordinate_picker_session(session_id):
    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.pop(session_id, None)


def claim_local_scroll_coordinate_picker_task(user_id, runner_id):
    cleanup_local_scroll_coordinate_picker_sessions(user_id=user_id, runner_id=runner_id)

    with LOCAL_SCROLL_COORDINATE_PICKER_LOCK:
        sessions = sorted(
            [
                session
                for session in LOCAL_SCROLL_COORDINATE_PICKER_SESSIONS.values()
                if session.get('user_id') == user_id and session.get('runner_id') == runner_id
            ],
            key=lambda item: item.get('created_at', 0),
        )
        for session in sessions:
            if session.get('state') == 'pending_start':
                session['state'] = 'starting'
                session['last_used_at'] = time.time()
                return {
                    'task_type': 'scroll_coordinate_picker',
                    'session_id': session['session_id'],
                    'action': 'start',
                    'browser': session.get('browser_name') or 'chromium',
                    'base_url': session['base_url'],
                    'picker_element_data': session.get('picker_element_data') or None,
                }

            command = session.get('command')
            if not command or command.get('status') != 'pending':
                continue

            command['status'] = 'claimed'
            session['last_used_at'] = time.time()
            return {
                'task_type': 'scroll_coordinate_picker',
                'session_id': session['session_id'],
                'action': command['action'],
                'field': command.get('field') or 'start',
                'page_index': command.get('page_index'),
                'command_sequence': command['sequence'],
                'browser': session.get('browser_name') or 'chromium',
                'base_url': session['base_url'],
                'picker_element_data': session.get('picker_element_data') or None,
            }

    return None


def report_local_scroll_coordinate_picker_task(
    user_id,
    runner_id,
    session_id,
    action,
    success,
    payload=None,
    error='',
    command_sequence=None,
):
    session = get_local_scroll_coordinate_picker_session(session_id, user_id)
    if session.get('runner_id') != runner_id:
        raise ValueError('本地执行器与坐标采集会话不匹配')

    session['last_used_at'] = time.time()
    if action == 'start':
        if success:
            session['state'] = 'ready'
            session['error'] = ''
        else:
            session['state'] = 'error'
            session['error'] = error or '本地执行器启动坐标采集浏览器失败'
        session.get('ready_event').set()
        return session

    command = session.get('command')
    if not command:
        raise ValueError('坐标采集命令不存在或已失效')
    if command_sequence and int(command_sequence) != int(command.get('sequence')):
        raise ValueError('坐标采集命令序号不匹配')
    if command.get('action') != action:
        raise ValueError('坐标采集命令类型不匹配')

    if success:
        command['status'] = 'completed'
        command['payload'] = payload or {}
        command['error'] = ''
        if action == 'close':
            session['state'] = 'closed'
    else:
        command['status'] = 'failed'
        command['error'] = error or '坐标采集执行失败'
        if action == 'close':
            session['state'] = 'error'

    command.get('event').set()
    return session
