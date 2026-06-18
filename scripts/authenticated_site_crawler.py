#!/usr/bin/env python
"""
Authenticated same-site crawler.

This script keeps one Playwright browser context for the full crawl so cookies,
localStorage, sessionStorage and bearer-token based sessions survive after login.
It discovers links from each rendered page and crawls same-site URLs breadth-first.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright


DEFAULT_WAIT_AFTER_LOAD_MS = 800
SKIP_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bmp",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".eot",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".map",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".pdf",
    ".png",
    ".rar",
    ".svg",
    ".tar",
    ".ttf",
    ".webm",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".zip",
}


@dataclass(frozen=True)
class CrawlResult:
    url: str
    final_url: str
    status: int | None
    title: str
    path: str | None
    skipped_reason: str | None = None


def normalize_url(raw_url: str, base_url: str | None = None) -> str | None:
    if not raw_url:
        return None

    value = raw_url.strip()
    if value.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
        return None

    if base_url:
        value = urljoin(base_url, value)

    value, _fragment = urldefrag(value)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",
        )
    )


def is_same_site(url: str, allowed_hosts: set[str]) -> bool:
    return urlparse(url).netloc.lower() in allowed_hosts


def looks_like_asset(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


def safe_filename(url: str, index: int) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "index"
    if parsed.query:
        path = f"{path}_{parsed.query}"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", path).strip("._")
    if not name:
        name = "index"
    return f"{index:04d}_{name[:140]}.html"


async def auto_login(
    page: Page,
    login_url: str,
    username: str | None,
    password: str | None,
    username_selector: str | None,
    password_selector: str | None,
    submit_selector: str | None,
    wait_for_url: str | None,
    wait_for_selector: str | None,
    manual_login: bool,
    login_timeout_ms: int,
) -> None:
    await page.goto(login_url, wait_until="domcontentloaded", timeout=login_timeout_ms)

    if manual_login:
        print("Manual login mode: complete login in the opened browser window.")
        if wait_for_selector:
            await page.wait_for_selector(wait_for_selector, timeout=login_timeout_ms)
        elif wait_for_url:
            await page.wait_for_url(wait_for_url, timeout=login_timeout_ms)
        else:
            input("Press Enter here after login succeeds...")
        return

    if not username or not password:
        raise ValueError("Automatic login requires --username and --password, or use --manual-login.")
    if not username_selector or not password_selector or not submit_selector:
        raise ValueError(
            "Automatic login requires --username-selector, --password-selector and --submit-selector."
        )

    await page.fill(username_selector, username)
    await page.fill(password_selector, password)
    await page.click(submit_selector)

    if wait_for_selector:
        await page.wait_for_selector(wait_for_selector, timeout=login_timeout_ms)
    if wait_for_url:
        await page.wait_for_url(wait_for_url, timeout=login_timeout_ms)
    if not wait_for_selector and not wait_for_url:
        try:
            await page.wait_for_load_state("networkidle", timeout=login_timeout_ms)
        except PlaywrightTimeoutError:
            pass


async def collect_links(page: Page) -> list[str]:
    links = await page.eval_on_selector_all(
        "a[href]",
        """elements => elements
            .map(element => element.href)
            .filter(Boolean)
        """,
    )
    return [str(link) for link in links]


async def crawl_url(
    page: Page,
    url: str,
    output_dir: Path,
    output_index: int,
    login_url_patterns: list[re.Pattern[str]],
    wait_after_load_ms: int,
) -> tuple[CrawlResult, list[str]]:
    response = None
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_load_state("networkidle", timeout=8_000)
    except PlaywrightTimeoutError:
        pass

    if wait_after_load_ms > 0:
        await page.wait_for_timeout(wait_after_load_ms)

    final_url = normalize_url(page.url) or page.url
    if any(pattern.search(final_url) for pattern in login_url_patterns):
        return (
            CrawlResult(
                url=url,
                final_url=final_url,
                status=response.status if response else None,
                title="",
                path=None,
                skipped_reason="redirected_to_login",
            ),
            [],
        )

    title = await page.title()
    html = await page.content()
    file_path = output_dir / safe_filename(final_url, output_index)
    file_path.write_text(html, encoding="utf-8")

    links = await collect_links(page)
    return (
        CrawlResult(
            url=url,
            final_url=final_url,
            status=response.status if response else None,
            title=title,
            path=str(file_path),
        ),
        links,
    )


async def run_crawl(args: argparse.Namespace) -> int:
    start_url = normalize_url(args.start_url)
    login_url = normalize_url(args.login_url)
    if not start_url or not login_url:
        raise ValueError("--start-url and --login-url must be absolute http(s) URLs.")

    allowed_hosts = {urlparse(start_url).netloc.lower()}
    for host in args.allowed_host:
        allowed_hosts.add(host.lower())

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    login_url_patterns = [re.compile(pattern, re.I) for pattern in args.login_url_pattern]

    visited: set[str] = set()
    queued: set[str] = {start_url}
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    results: list[CrawlResult] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        context = await browser.new_context(storage_state=args.storage_state if args.storage_state else None)
        page = await context.new_page()

        if not args.storage_state:
            password = args.password
            if args.password_env:
                password = os.environ.get(args.password_env)
                if password is None:
                    raise ValueError(f"Environment variable {args.password_env!r} is not set.")

            await auto_login(
                page=page,
                login_url=login_url,
                username=args.username,
                password=password,
                username_selector=args.username_selector,
                password_selector=args.password_selector,
                submit_selector=args.submit_selector,
                wait_for_url=args.wait_for_url,
                wait_for_selector=args.wait_for_selector,
                manual_login=args.manual_login,
                login_timeout_ms=args.login_timeout_ms,
            )
            await context.storage_state(path=output_dir / "storage_state.json")

        while queue and len(visited) < args.max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            if depth > args.max_depth:
                results.append(CrawlResult(url, url, None, "", None, "max_depth"))
                continue
            if looks_like_asset(url):
                results.append(CrawlResult(url, url, None, "", None, "asset"))
                continue

            print(f"[{len(visited)}/{args.max_pages}] depth={depth} {url}")
            result, links = await crawl_url(
                page=page,
                url=url,
                output_dir=output_dir,
                output_index=len(results) + 1,
                login_url_patterns=login_url_patterns,
                wait_after_load_ms=args.wait_after_load_ms,
            )
            results.append(result)

            if result.skipped_reason:
                continue

            for raw_link in links:
                next_url = normalize_url(raw_link, result.final_url)
                if not next_url:
                    continue
                if next_url in visited or next_url in queued:
                    continue
                if not is_same_site(next_url, allowed_hosts):
                    continue
                if looks_like_asset(next_url):
                    continue
                queued.add(next_url)
                queue.append((next_url, depth + 1))

        await browser.close()

    manifest = {
        "start_url": start_url,
        "allowed_hosts": sorted(allowed_hosts),
        "max_depth": args.max_depth,
        "max_pages": args.max_pages,
        "visited_count": len(visited),
        "saved_count": sum(1 for result in results if result.path),
        "results": [result.__dict__ for result in results],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {manifest['saved_count']} pages to {output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl same-site pages after login.")
    parser.add_argument("--login-url", required=True, help="Login page URL.")
    parser.add_argument("--start-url", required=True, help="First authenticated page to crawl.")
    parser.add_argument("--output-dir", default="download/crawled_pages", help="Directory for HTML output.")
    parser.add_argument("--username", help="Login username.")
    parser.add_argument("--password", help="Login password.")
    parser.add_argument("--password-env", help="Read login password from this environment variable.")
    parser.add_argument("--username-selector", help="CSS selector for username input.")
    parser.add_argument("--password-selector", help="CSS selector for password input.")
    parser.add_argument("--submit-selector", help="CSS selector for login submit button.")
    parser.add_argument("--wait-for-url", help="URL glob to wait for after login, for example **/dashboard**.")
    parser.add_argument("--wait-for-selector", help="CSS selector that proves login succeeded.")
    parser.add_argument("--manual-login", action="store_true", help="Let a user log in manually in the browser.")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly.")
    parser.add_argument("--storage-state", help="Reuse an existing Playwright storage_state.json.")
    parser.add_argument("--allowed-host", action="append", default=[], help="Extra host allowed for crawling.")
    parser.add_argument(
        "--login-url-pattern",
        action="append",
        default=[r"/login\b", r"/auth/login\b"],
        help="Regex that identifies a login page redirect. Can be repeated.",
    )
    parser.add_argument("--max-depth", type=int, default=3, help="Maximum link depth.")
    parser.add_argument("--max-pages", type=int, default=200, help="Maximum pages to visit.")
    parser.add_argument("--login-timeout-ms", type=int, default=120_000, help="Login timeout in milliseconds.")
    parser.add_argument(
        "--wait-after-load-ms",
        type=int,
        default=DEFAULT_WAIT_AFTER_LOAD_MS,
        help="Extra wait after page load before extracting links.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_crawl(args))


if __name__ == "__main__":
    raise SystemExit(main())
