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
            print('Runner stopped by user')
            break
        except Exception as exc:
            print(f'Runner loop error: {exc}')
            time.sleep(error_sleep)


if __name__ == '__main__':
    main()
