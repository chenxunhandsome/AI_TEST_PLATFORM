"""
Playwright自动化测试执行引擎
用于驱动真实浏览器执行UI自动化测试
"""
import asyncio
import base64
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeout
import logging
from .variable_resolver import resolve_variables, set_runtime_variable
from .browser_config import (
    get_chromium_window_size_argument,
    resolve_browser_resolution,
)

logger = logging.getLogger(__name__)
RUNTIME_VARIABLE_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def append_runtime_variable_log(step, log, value):
    save_as = str(getattr(step, 'save_as', '') or '').strip()
    if not save_as:
        return log

    if not RUNTIME_VARIABLE_NAME_RE.match(save_as):
        return f"{log}\n  - 跳过变量存储: 变量名 '{save_as}' 不合法"

    set_runtime_variable(save_as, value)
    return f"{log}\n  - 已存储变量: ${{{save_as}}} = '{value}'"

class PlaywrightTestEngine:
    """Playwright测试执行引擎"""

    def __init__(self, browser_type='chromium', headless=True, browser_width=None, browser_height=None):
        """
        初始化测试引擎

        Args:
            browser_type: 浏览器类型 (chromium, firefox, webkit)
            headless: 是否无头模式
        """
        self.browser_type = browser_type
        self.headless = headless
        self.browser_width, self.browser_height = resolve_browser_resolution(
            browser_width=browser_width,
            browser_height=browser_height,
        )
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._recent_dialog = None

    async def _apply_window_size(self):
        if self.page is None:
            return

        try:
            await self.page.set_viewport_size({
                'width': self.browser_width,
                'height': self.browser_height,
            })
        except Exception:
            logger.debug("设置 Playwright viewport 失败，保留当前配置", exc_info=True)

        if self.headless:
            return

        if self.browser_type == 'chromium' and self.context is not None:
            try:
                session = await self.context.new_cdp_session(self.page)
                window_info = await session.send('Browser.getWindowForTarget')
                window_id = window_info.get('windowId')
                if window_id is not None:
                    try:
                        await session.send(
                            'Browser.setWindowBounds',
                            {'windowId': window_id, 'bounds': {'windowState': 'normal'}}
                        )
                    except Exception:
                        logger.debug("恢复 Chromium 窗口到 normal 状态失败，继续尝试设置尺寸", exc_info=True)

                    await session.send(
                        'Browser.setWindowBounds',
                        {
                            'windowId': window_id,
                            'bounds': {
                                'left': 0,
                                'top': 0,
                                'width': self.browser_width,
                                'height': self.browser_height,
                            }
                        }
                    )
                    return
            except Exception:
                logger.debug("通过 CDP 设置 Chromium 窗口尺寸失败，回退到 window.resizeTo", exc_info=True)

        try:
            await self.page.evaluate(
                """([width, height]) => {
                    try {
                        window.moveTo(0, 0);
                        window.resizeTo(width, height);
                        return { outerWidth: window.outerWidth, outerHeight: window.outerHeight };
                    } catch (error) {
                        return null;
                    }
                }""",
                [self.browser_width, self.browser_height],
            )
        except Exception:
            logger.debug("通过 window.resizeTo 设置浏览器窗口尺寸失败", exc_info=True)

    async def _handle_dialog(self, dialog):
        self._recent_dialog = {
            'type': getattr(dialog, 'type', 'dialog'),
            'message': getattr(dialog, 'message', ''),
            'timestamp': time.time(),
        }
        try:
            await dialog.dismiss()
        except Exception:
            await dialog.accept()

    def _register_page_handlers(self, page: Optional[Page]):
        if page is None or not hasattr(page, 'on'):
            return
        page.on('dialog', lambda dialog: asyncio.create_task(self._handle_dialog(dialog)))

    def _register_context_handlers(self):
        if self.context is None or not hasattr(self.context, 'on'):
            return
        self.context.on('page', self._register_page_handlers)

    def _consume_recent_dialog(self, window_seconds: float = 2.0):
        dialog = self._recent_dialog
        self._recent_dialog = None
        if not dialog:
            return None
        if time.time() - dialog.get('timestamp', 0) > window_seconds:
            return None
        return dialog

    async def _close_current_page(self, start_time: float):
        recent_dialog = self._consume_recent_dialog()
        dialog_log_lines = []
        if recent_dialog:
            dialog_log_lines = [
                "✓ 已关闭浏览器弹窗",
                f"  - 弹窗类型: {recent_dialog['type']}",
                f"  - 弹窗内容: {recent_dialog['message']}",
            ]

        if self.context is None or self.page is None:
            return False, "✗ 当前没有可关闭的页面", None

        current_page = self.page
        pages = [page for page in self.context.pages if not page.is_closed()]
        if current_page.is_closed():
            if not pages:
                return False, "✗ 当前页面已关闭，且没有可切换的页面", None
            self.page = pages[-1]
            await self.page.bring_to_front()
            execution_time = round(time.time() - start_time, 2)
            log = "✓ 当前页面已关闭，已切换到可用页面\n"
            log += f"  - 页面数量: {len(pages)}\n"
            log += f"  - 执行时间: {execution_time}秒"
            return True, log, None

        closed_url = current_page.url
        if len(pages) <= 1:
            replacement_page = await self.context.new_page()
            self._register_page_handlers(replacement_page)
            try:
                await replacement_page.goto('about:blank', wait_until='domcontentloaded', timeout=5000)
            except Exception:
                pass
            await current_page.close()
            self.page = replacement_page
            await self.page.bring_to_front()
            execution_time = round(time.time() - start_time, 2)
            log = ""
            if dialog_log_lines:
                log += "\n".join(dialog_log_lines) + "\n"
            log += "✓ 已关闭当前页面并保留会话\n"
            log += f"  - 已关闭页面: {closed_url}\n"
            log += f"  - 当前页面: {self.page.url}\n"
            log += f"  - 执行时间: {execution_time}秒"
            return True, log, None

        await current_page.close()
        remaining_pages = [page for page in self.context.pages if not page.is_closed()]
        if not remaining_pages:
            return False, "✗ 当前页面关闭后未找到可用页面", None

        self.page = remaining_pages[-1]
        await self.page.bring_to_front()
        execution_time = round(time.time() - start_time, 2)
        log = ""
        if dialog_log_lines:
            log += "\n".join(dialog_log_lines) + "\n"
        log += "✓ 已关闭当前页面\n"
        log += f"  - 已关闭页面: {closed_url}\n"
        log += f"  - 当前页面: {self.page.url}\n"
        log += f"  - 执行时间: {execution_time}秒"
        return True, log, None

    async def start(self):
        """启动浏览器"""
        try:
            self.playwright = await async_playwright().start()

            # 根据浏览器类型选择启动方式
            if self.browser_type == 'chromium':
                browser_launcher = self.playwright.chromium
            elif self.browser_type == 'firefox':
                browser_launcher = self.playwright.firefox
            elif self.browser_type == 'webkit':
                browser_launcher = self.playwright.webkit
            else:
                browser_launcher = self.playwright.chromium

            # 启动浏览器
            launch_args = [
                '--disable-blink-features=AutomationControlled',  # 避免被检测
                '--ignore-certificate-errors',  # 忽略证书错误
                '--allow-insecure-localhost',  # 允许不安全localhost
                '--disable-web-security',  # 禁用web安全限制（跨域）
            ]
            launch_args.append(
                get_chromium_window_size_argument(
                    browser_width=self.browser_width,
                    browser_height=self.browser_height,
                )
            )
            if self.browser_type == 'chromium':
                launch_args.extend([
                    '--disable-translate',
                    '--disable-features=Translate,TranslateUI',
                    '--lang=zh-CN',
                ])
            self.browser = await browser_launcher.launch(
                headless=self.headless,
                args=launch_args
            )

            # 创建浏览器上下文
            context_options = {
                'viewport': {'width': self.browser_width, 'height': self.browser_height},
                'screen': {'width': self.browser_width, 'height': self.browser_height},
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'locale': 'zh-CN',
            }
            if self.browser_type == 'chromium':
                context_options['extra_http_headers'] = {
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
                }
            self.context = await self.browser.new_context(**context_options)

            # 创建页面
            self.page = await self.context.new_page()
            self._register_context_handlers()
            self._register_page_handlers(self.page)
            await self._apply_window_size()

            logger.info(f"浏览器启动成功: {self.browser_type}, headless={self.headless}")

        except Exception as e:
            logger.error(f"启动浏览器失败: {str(e)}")
            raise

    async def stop(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器失败: {str(e)}")

    def _build_locator(self, locator_strategy: str, locator_value: str):
        locator_strategy = (locator_strategy or 'css').lower()
        locator_value = locator_value or ''

        if locator_strategy == 'id':
            return self.page.locator(f'#{locator_value}')
        if locator_strategy in ['css', 'css selector']:
            if any(keyword in locator_value.lower() for keyword in ['dropdown', 'el-select', ':has(', 'li']):
                if 'visible=true' not in locator_value:
                    return self.page.locator(f"{locator_value} >> visible=true").first
                return self.page.locator(locator_value).first
            return self.page.locator(locator_value)
        if locator_strategy == 'xpath':
            if any(keyword in locator_value.lower() for keyword in ['dropdown', 'el-select', ':has(', 'li']):
                if 'visible=true' not in locator_value:
                    return self.page.locator(f"xpath={locator_value} >> visible=true").first
                return self.page.locator(f"xpath={locator_value}").first
            if '[' in locator_value and ']' in locator_value:
                return self.page.locator(f'xpath={locator_value}')
            return self.page.locator(f'xpath={locator_value}').first
        if locator_strategy == 'text':
            return self.page.get_by_text(locator_value)
        if locator_strategy == 'name':
            return self.page.locator(f'[name="{locator_value}"]')
        if locator_strategy == 'placeholder':
            return self.page.get_by_placeholder(locator_value)
        if locator_strategy == 'role':
            return self.page.get_by_role(locator_value)
        if locator_strategy == 'label':
            return self.page.get_by_label(locator_value)
        if locator_strategy == 'title':
            return self.page.get_by_title(locator_value)
        if locator_strategy == 'test-id':
            return self.page.get_by_test_id(locator_value)
        return self.page.locator(locator_value)

    def _resolve_drag_target_data(self, raw_input) -> Dict[str, str]:
        if not raw_input:
            raise ValueError('拖拽步骤缺少目标元素配置')

        payload = raw_input
        if isinstance(raw_input, str):
            try:
                payload = json.loads(raw_input)
            except json.JSONDecodeError as exc:
                raise ValueError('拖拽目标配置不是有效的 JSON') from exc

        if not isinstance(payload, dict):
            raise ValueError('拖拽目标配置格式不正确')

        target_element_id = payload.get('target_element_id') or payload.get('element_id')
        if target_element_id:
            try:
                from .models import Element
                target_element = Element.objects.select_related('locator_strategy').get(id=int(target_element_id))
                return {
                    'locator_strategy': target_element.locator_strategy.name if target_element.locator_strategy else 'css',
                    'locator_value': target_element.locator_value,
                    'name': target_element.name,
                }
            except (ValueError, TypeError, Element.DoesNotExist):
                pass

        locator_strategy = payload.get('target_locator_strategy') or payload.get('locator_strategy')
        locator_value = payload.get('target_locator_value') or payload.get('locator_value')
        if not locator_strategy or not locator_value:
            raise ValueError('拖拽目标元素缺少定位信息')

        return {
            'locator_strategy': locator_strategy,
            'locator_value': locator_value,
            'name': payload.get('target_element_name') or payload.get('name') or '目标元素',
        }

    async def execute_step(self, step, element_data: Dict) -> Tuple[bool, str, Optional[str]]:
        """
        执行单个测试步骤

        Args:
            step: 测试步骤对象
            element_data: 元素数据字典 {locator_strategy, locator_value, name}

        Returns:
            (是否成功, 日志信息, 截图base64)
        """
        action_type = step.action_type
        
        # 预先解析变量
        resolved_input_value = step.input_value
        if step.input_value:
            resolved_input_value = resolve_variables(step.input_value)
            
        resolved_assert_value = step.assert_value
        if step.assert_value:
            resolved_assert_value = resolve_variables(step.assert_value)
            
        start_time = time.time()
        screenshot_base64 = None

        try:
            # wait和screenshot操作不需要元素定位器
            if action_type == 'wait':
                wait_seconds = step.wait_time / 1000 if step.wait_time else 1
                await asyncio.sleep(wait_seconds)
                execution_time = round(time.time() - start_time, 2)
                log = f"✓ 固定等待 {wait_seconds} 秒完成 - 耗时 {execution_time}秒"
                return True, log, None

            elif action_type == 'screenshot':
                screenshot = await self.page.screenshot()
                screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                execution_time = round(time.time() - start_time, 2)
                log = f"✓ 截图成功\n"
                log += f"  - 截图范围: 整个页面\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, screenshot_base64

            elif action_type == 'switchTab':
                # 切换标签页
                # 获取超时时间
                if step.wait_time:
                    timeout = max(step.wait_time / 1000, 5.0)
                else:
                    timeout = 5.0
                
                start_wait = time.time()
                current_page = self.page
                target_index = -1
                
                while True:
                    pages = [page for page in self.context.pages if not page.is_closed()]
                    if (
                        not (resolved_input_value and str(resolved_input_value).isdigit())
                        and current_page in pages
                        and len(pages) > 1
                        and pages[-1] == current_page
                    ):
                        pages = [current_page] + [page for page in pages if page != current_page]
                    target_index = -1  # 默认切换到最新标签页
                    should_switch = False
                    
                    if resolved_input_value and str(resolved_input_value).isdigit():
                        # 指定索引的情况
                        idx = int(resolved_input_value)
                        if 0 <= idx < len(pages):
                            target_index = idx
                            should_switch = True
                    else:
                        # 切换到最新的情况
                        target_index = -1
                        # 如果最新的页面不是当前页面，说明有新标签页，或者是切换到其他已存在的标签页
                        if pages[-1] != current_page:
                            should_switch = True
                        # 如果只有一个页面，且就是当前页，可能是在等待新标签页打开
                        elif len(pages) == 1 and pages[0] == current_page:
                            should_switch = False
                        # 如果有多个页面，但最新的就是当前页，可能是想留在当前页，也可能是等待更新的
                        else:
                            should_switch = False

                    if should_switch:
                        break
                    
                    if time.time() - start_wait > timeout:
                        # 超时了，就切换到当前能找到的那个（Best Effort）
                        break
                        
                    await asyncio.sleep(0.5)
                
                # 获取目标页面
                if target_index == -1:
                    target_page = pages[-1]
                    final_target_index = len(pages) - 1
                else:
                    target_page = pages[target_index]
                    final_target_index = target_index

                # 将目标页面设为当前活动页面
                await target_page.bring_to_front()
                try:
                    await target_page.wait_for_load_state('networkidle', timeout=10000)
                except Exception:
                    try:
                        await target_page.wait_for_load_state('domcontentloaded', timeout=5000)
                    except Exception:
                        pass
                if hasattr(target_page, 'wait_for_timeout'):
                    await target_page.wait_for_timeout(1500)
                # 更新引擎的当前页面引用
                self.page = target_page
                
                execution_time = round(time.time() - start_time, 2)
                log = f"✓ 切换标签页成功\n"
                log += f"  - 目标索引: {final_target_index}\n"
                log += f"  - 页面标题: {await self.page.title()}\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'closeCurrentPage':
                return await self._close_current_page(start_time)

            # 其他操作需要元素定位器
            # 获取元素定位器
            locator_strategy = element_data.get('locator_strategy', 'css')
            locator_value = element_data.get('locator_value', '')
            element_name = element_data.get('name', '未知元素')

            # 获取强制操作选项（用于visibility:hidden的元素）
            force_action = element_data.get('force_action', False)

            # 计算超时时间：优先使用元素的wait_timeout（秒），其次使用步骤的wait_time（毫秒）
            # 如果元素有wait_timeout，转换为毫秒；否则使用步骤的wait_time
            element_wait_timeout = element_data.get('wait_timeout')  # 秒
            if element_wait_timeout is not None and element_wait_timeout > 0:
                timeout_ms = element_wait_timeout * 1000  # 转换为毫秒
            elif step.wait_time:
                timeout_ms = step.wait_time
            else:
                timeout_ms = 5000  # 默认5秒

            # 根据定位策略获取元素
            if locator_strategy.lower() == 'id':
                locator = self.page.locator(f'#{locator_value}')
            elif locator_strategy.lower() in ['css', 'css selector']:
                # CSS 定位器，对于可能匹配多个元素的情况，添加 .first
                # 特别是下拉框选项，可能有多个同名选项
                if any(keyword in locator_value.lower() for keyword in ['dropdown', 'el-select', ':has(', 'li']):
                    # 如果是下拉框选项，强制只查找可见元素
                    if 'visible=true' not in locator_value:
                        locator = self.page.locator(f"{locator_value} >> visible=true").first
                    else:
                        locator = self.page.locator(locator_value).first
                else:
                    locator = self.page.locator(locator_value)
            elif locator_strategy.lower() == 'xpath':
                # XPath 定位器
                # 如果是下拉框选项，强制只查找可见元素
                if any(keyword in locator_value.lower() for keyword in ['dropdown', 'el-select', ':has(', 'li']):
                    if 'visible=true' not in locator_value:
                        locator = self.page.locator(f"xpath={locator_value} >> visible=true").first
                    else:
                        locator = self.page.locator(f"xpath={locator_value}").first
                # 如果 XPath 已经包含索引 [n]，不要添加 .first（会冲突）
                elif '[' in locator_value and ']' in locator_value:
                    locator = self.page.locator(f'xpath={locator_value}')
                else:
                    # 如果没有索引，添加 .first 避免 strict mode violation
                    locator = self.page.locator(f'xpath={locator_value}').first
            elif locator_strategy.lower() == 'text':
                locator = self.page.get_by_text(locator_value)
            elif locator_strategy.lower() == 'name':
                locator = self.page.locator(f'[name="{locator_value}"]')
            elif locator_strategy.lower() == 'placeholder':
                locator = self.page.get_by_placeholder(locator_value)
            elif locator_strategy.lower() == 'role':
                locator = self.page.get_by_role(locator_value)
            elif locator_strategy.lower() == 'label':
                locator = self.page.get_by_label(locator_value)
            elif locator_strategy.lower() == 'title':
                locator = self.page.get_by_title(locator_value)
            elif locator_strategy.lower() == 'test-id':
                locator = self.page.get_by_test_id(locator_value)
            else:
                # 默认使用CSS选择器
                locator = self.page.locator(locator_value)

            # 执行操作
            execution_time = 0

            if action_type == 'click':
                # 检测是否是原生HTML select的option元素（优先检测，因为option元素特殊）
                is_native_select_option = (
                    ('option[' in locator_value or ' > option' in locator_value or '//option' in locator_value) or
                    ('select' in locator_value.lower() and 'option' in locator_value.lower())
                )

                # 对于原生HTML select的option，使用select_option方法
                if is_native_select_option:
                    logger.info(f"检测到原生HTML select元素，使用select_option方法...")

                    # 提取select的定位器和option的value
                    # 例如：select[name="my-select"] option[value="1"]
                    # 需要提取：select[name="my-select"] 和 value="1"

                    import re

                    # 提取option的value值
                    option_value_match = re.search(r'option\[value=["\']([^"\']+)["\']\]', locator_value)
                    option_value_xpath_match = re.search(r'option\[@value=["\']([^"\']+)["\']\]', locator_value)

                    option_value = None
                    if option_value_match:
                        option_value = option_value_match.group(1)
                    elif option_value_xpath_match:
                        option_value = option_value_xpath_match.group(1)
                    else:
                        # 尝试其他格式
                        option_value = '1'  # 默认值

                    # 构造select元素的定位器（去掉option部分）
                    select_locator_value = re.sub(r'\s*>\s*option\[.*?\]', '', locator_value)
                    select_locator_value = re.sub(r'\s+option\[.*?\]', '', select_locator_value)
                    select_locator_value = re.sub(r'//option\[.*?\]', '', select_locator_value)

                    logger.info(f"Select定位器: {select_locator_value}, Option值: {option_value}")

                    try:
                        # 构造select元素的locator
                        if locator_strategy.lower() == 'xpath':
                            # XPath: //select[@name='my-select']/option[@value='1']
                            # 提取select部分
                            select_match = re.match(r'^(//.*?select)(?:/option)?', locator_value)
                            if select_match:
                                select_locator_value = select_match.group(1)
                            else:
                                select_locator_value = locator_value.split('/')[0]
                            select_locator = self.page.locator(f"xpath={select_locator_value}")
                        else:
                            # CSS: select[name="my-select"] option[value="1"]
                            select_locator = self.page.locator(select_locator_value)

                        # 使用select_option方法
                        await select_locator.select_option(value=option_value, timeout=timeout_ms)

                        execution_time = round(time.time() - start_time, 2)
                        log = f"✓ 选择下拉框选项 '{element_name}' 成功\n"
                        log += f"  - Select定位器: {select_locator_value}\n"
                        log += f"  - 选中值: {option_value}\n"
                        log += f"  - 方法: select_option() (原生HTML select)\n"
                        log += f"  - 执行时间: {execution_time}秒"
                        return True, log, None

                    except Exception as e:
                        logger.error(f"select_option失败: {e}")
                        # 如果失败，继续尝试普通点击
                        pass

                # 对于下拉框选项，需要特殊处理
                # 通过定位器特征自动识别下拉框选项
                is_dropdown_option = (
                    'dropdown' in locator_value.lower() or
                    'el-select' in locator_value.lower() or
                    '下拉' in element_name or
                    '选项' in element_name or
                    'role="option"' in locator_value.lower() or
                    'el-select-dropdown__item' in locator_value.lower() or  # Element Plus 下拉框
                    ('//li' in locator_value and 'span=' in locator_value)  # XPath 下拉框模式
                )
                
                # 检测是否是点击 el-select 容器（下拉框触发器）
                is_select_trigger = ('el-select' in locator_value.lower() and 
                                    'ancestor::' in locator_value.lower() and
                                    'el-select-dropdown' not in locator_value.lower())
                
                if is_select_trigger:
                    # el-select 容器：点击内部的真正触发器，触发完整事件链
                    logger.info(f"检测到 el-select 容器，使用 Playwright 原生点击...")
                    try:
                        # 等待容器出现
                        await locator.wait_for(state='visible', timeout=timeout_ms)
                        # 点击内部的 wrapper 或 input（使用 Playwright 原生点击，会触发完整事件）
                        wrapper_locator = locator.locator('.el-select__wrapper, input').first
                        await wrapper_locator.click(timeout=timeout_ms, no_wait_after=False)
                        # 等待下拉框展开动画
                        await asyncio.sleep(0.5)
                        
                        execution_time = round(time.time() - start_time, 2)
                        log = f"✓ 点击下拉框触发器 '{element_name}' 成功\n"
                        log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                        log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                        log += f"  - 特殊处理: Playwright原生点击内部触发器 + 等待展开\n"
                        log += f"  - 执行时间: {execution_time}秒"
                        return True, log, None
                    except Exception as e:
                        logger.warning(f"Playwright 点击失败，尝试其他方法: {e}")
                        
                        # 备用方案：使用完整的事件链
                        try:
                            await locator.locator('.el-select__wrapper, input').first.evaluate("""
                                element => {
                                    const events = [
                                        new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }),
                                        new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }),
                                        new MouseEvent('click', { bubbles: true, cancelable: true, view: window })
                                    ];
                                    events.forEach(event => element.dispatchEvent(event));
                                }
                            """)
                            await asyncio.sleep(0.5)
                            execution_time = round(time.time() - start_time, 2)
                            log = f"✓ 点击下拉框触发器 '{element_name}' 成功（事件链）\n"
                            log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                            log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                            log += f"  - 执行时间: {execution_time}秒"
                            return True, log, None
                        except Exception as e2:
                            logger.error(f"所有点击方法都失败: {e2}")
                            raise
                
                elif is_dropdown_option:
                    # 下拉框选项：需要特殊处理，确保能正确触发 Vue/Element Plus 的 v-model 更新
                    logger.info(f"检测到下拉框选项，使用 Playwright + Vue 数据更新策略...")
                    
                    # 等待下拉框完全展开并渲染
                    await asyncio.sleep(0.8)
                    
                    try:
                        # 等待元素在 DOM 中（不要求可见）
                        await locator.wait_for(state='attached', timeout=timeout_ms)
                        logger.info(f"元素已在 DOM 中，执行 Vue 数据更新...")
                        
                        # 策略：直接通过 page.evaluate() 操作，绕过 locator 的 actionability 检查
                        # locator.evaluate() 会等待元素可见，但下拉框选项可能是隐藏的
                        # 所以我们使用 page.evaluate() 并传递定位器表达式
                        
                        # 根据定位策略构造 JavaScript 选择器
                        if locator_strategy.lower() == 'xpath':
                            js_selector_code = f"""
                                const xpath = {repr(locator_value)};
                                const result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                                let element = null;
                                for (let i = 0; i < result.snapshotLength; i++) {{
                                    const node = result.snapshotItem(i);
                                    // 检查可见性: offsetParent 不为 null (且不是 fixed 定位) 或者 getComputedStyle display != none
                                    if (node.offsetParent !== null || window.getComputedStyle(node).display !== 'none') {{
                                        element = node;
                                        break;
                                    }}
                                }}
                            """
                        elif locator_strategy.lower() == 'css selector':
                            js_selector_code = f"""
                                const elements = document.querySelectorAll({repr(locator_value)});
                                let element = null;
                                for (const el of elements) {{
                                    if (el.offsetParent !== null || window.getComputedStyle(el).display !== 'none') {{
                                        element = el;
                                        break;
                                    }}
                                }}
                            """
                        else:
                            # 其他策略：尝试作为 CSS 选择器
                            js_selector_code = f"""
                                const elements = document.querySelectorAll({repr(locator_value)});
                                let element = null;
                                for (const el of elements) {{
                                    if (el.offsetParent !== null || window.getComputedStyle(el).display !== 'none') {{
                                        element = el;
                                        break;
                                    }}
                                }}
                            """
                        
                        # 构造基础定位器（不带 visible=true，因为我们要手动遍历）
                        base_locator_value = locator_value.replace(' >> visible=true', '')
                        
                        if locator_strategy.lower() == 'xpath':
                            if not base_locator_value.startswith('xpath='):
                                candidates = self.page.locator(f"xpath={base_locator_value}")
                            else:
                                candidates = self.page.locator(base_locator_value)
                        elif locator_strategy.lower() == 'css selector':
                            candidates = self.page.locator(base_locator_value)
                        else:
                            # 其他策略暂按 CSS 处理
                            candidates = self.page.locator(base_locator_value)
                        
                        # 获取匹配元素数量
                        count = await candidates.count()
                        logger.info(f"找到 {count} 个匹配元素，开始寻找可见元素...")
                        
                        found_visible = False
                        for i in range(count):
                            candidate = candidates.nth(i)
                            if await candidate.is_visible():
                                logger.info(f"找到第 {i+1} 个元素是可见的，执行点击...")
                                try:
                                    await candidate.click(timeout=timeout_ms)
                                    found_visible = True
                                    method_desc = f"iterative-click(index={i})"
                                    break
                                except Exception as e:
                                    logger.warning(f"点击第 {i+1} 个元素失败: {e}")
                        
                        if not found_visible:
                            logger.warning("未找到可见的下拉框选项元素，尝试点击第一个...")
                            try:
                                await candidates.first.click(force=True, timeout=timeout_ms)
                                method_desc = "fallback-force-click"
                            except Exception as e:
                                logger.error(f"强制点击失败: {e}")
                                raise e

                        # 检查并关闭多选下拉框
                        try:
                            await asyncio.sleep(0.5)
                            dropdown = self.page.locator('.el-select-dropdown').first
                            if await dropdown.is_visible():
                                logger.info(f"多选下拉框未自动关闭，点击空白处关闭...")
                                await self.page.click('body', position={'x': 10, 'y': 10}, timeout=3000)
                                auto_close_msg = " + 自动关闭"
                            else:
                                auto_close_msg = ""
                        except:
                            auto_close_msg = ""
                        
                        execution_time = round(time.time() - start_time, 2)
                        log = f"✓ 点击下拉框选项 '{element_name}' 成功（{method_desc}）\n"
                        log += f"  - 定位器: {locator_strategy}={base_locator_value}\n"
                        log += f"  - 匹配数量: {count}\n"
                        log += f"  - 执行方法: {method_desc}{auto_close_msg}\n"
                        log += f"  - 执行时间: {execution_time}秒"
                        return True, log, None
                        
                        logger.info(f"JS执行结果: {js_result}")
                        
                        # 等待 Vue 响应式更新完成
                        await asyncio.sleep(0.8)
                        
                        # 检查并关闭多选下拉框
                        try:
                            dropdown = self.page.locator('.el-select-dropdown').first
                            if await dropdown.is_visible():
                                logger.info(f"多选下拉框未自动关闭，点击空白处关闭...")
                                await self.page.click('body', position={'x': 10, 'y': 10}, timeout=3000)
                                await asyncio.sleep(0.5)
                                auto_close_msg = " + 自动关闭"
                            else:
                                auto_close_msg = ""
                        except:
                            auto_close_msg = ""
                        
                        execution_time = round(time.time() - start_time, 2)
                        method_desc = js_result.get('method', 'unknown') if isinstance(js_result, dict) else 'unknown'
                        log = f"✓ 点击下拉框选项 '{element_name}' 成功（{method_desc})\n"
                        log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                        log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                        log += f"  - 更新方法: {method_desc}{auto_close_msg}\n"
                        if isinstance(js_result, dict) and 'allValues' in js_result:
                            log += f"  - 当前选中值: {js_result['allValues']}\n"
                        log += f"  - 执行时间: {execution_time}秒"
                        return True, log, None
                    except Exception as e:
                        logger.error(f"下拉框选项点击失败: {e}")
                        execution_time = round(time.time() - start_time, 2)

                        # 构建详细的错误日志
                        error_log = f"✗ 点击下拉框选项 '{element_name}' 失败\n"
                        error_log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                        error_log += f"  - 执行时间: {execution_time}秒\n"
                        error_log += f"  - 错误: {str(e)}\n\n"
                        error_log += "建议解决方案:\n"
                        error_log += "1. 检查元素是否在下拉框展开后才出现在 DOM 中\n"
                        error_log += "2. 尝试在点击下拉框后增加等待时间（添加 wait 步骤，等待2000ms）\n"
                        error_log += "3. 使用 Playwright get_by_text 定位：文本=无忧行-鸿蒙APP\n"
                        error_log += "4. 检查 Vue DevTools 确认组件结构是否与代码匹配"

                        # 尝试捕获截图
                        screenshot_base64 = None
                        try:
                            screenshot = await self.page.screenshot()
                            screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        except:
                            pass

                        # 返回: (是否成功, 日志信息, 截图base64)
                        return False, error_log, screenshot_base64
                else:
                    # 普通元素：正常点击
                    # 如果启用了强制操作，先等待元素在 DOM 中，不要求可见
                    if force_action:
                        try:
                            await locator.wait_for(state='attached', timeout=timeout_ms)
                        except:
                            pass  # 如果已经在 DOM 中，继续
                    
                    await locator.click(timeout=timeout_ms, force=force_action)
                    execution_time = round(time.time() - start_time, 2)
                    log = f"✓ 点击元素 '{element_name}' 成功\n"
                    log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                    log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                    if force_action:
                        log += f"  - 强制操作: 是（跳过可见性检查，等待attached）\n"
                    log += f"  - 执行时间: {execution_time}秒"
                    return True, log, None

            elif action_type == 'fill':
                await locator.fill(resolved_input_value, timeout=timeout_ms, force=force_action)
                execution_time = round(time.time() - start_time, 2)

                # 输入成功后短暂等待，确保表单验证生效
                # 特别是在服务器环境下，需要给Vue/React等框架时间处理
                await asyncio.sleep(0.3)

                log = f"✓ 在元素 '{element_name}' 中输入文本成功\n"
                log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                if resolved_input_value != step.input_value:
                    log += f"  - 变量解析: '{step.input_value}' => '{resolved_input_value}'\n"
                log += f"  - 输入内容: '{resolved_input_value}'\n"
                log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                if force_action:
                    log += f"  - 强制操作: 是（忽略可见性检查）\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'fillAndEnter':
                await locator.fill(resolved_input_value, timeout=timeout_ms, force=force_action)
                await locator.press('Enter', timeout=timeout_ms)
                execution_time = round(time.time() - start_time, 2)

                # 输入回车后短暂等待，确保页面或表单事件有时间响应
                await asyncio.sleep(0.3)

                log = f"✓ 在元素 '{element_name}' 中输入文本并按回车成功\n"
                log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                if resolved_input_value != step.input_value:
                    log += f"  - 变量解析: '{step.input_value}' => '{resolved_input_value}'\n"
                log += f"  - 输入内容: '{resolved_input_value}'\n"
                log += "  - 按键: Enter\n"
                log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                if force_action:
                    log += "  - 强制操作: 是（fill 时使用 force）\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'getText':
                text = await locator.inner_text(timeout=timeout_ms)
                execution_time = round(time.time() - start_time, 2)
                log = f"✓ 获取元素 '{element_name}' 的文本成功\n"
                log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                log += f"  - 文本内容: '{text}'\n"
                log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'waitFor':
                await locator.wait_for(state='visible', timeout=timeout_ms)
                execution_time = round(time.time() - start_time, 2)
                log = f"✓ 等待元素 '{element_name}' 出现成功\n"
                log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                log += f"  - 等待时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'hover':
                await locator.hover(timeout=timeout_ms, force=force_action)
                execution_time = round(time.time() - start_time, 2)
                log = f"✓ 在元素 '{element_name}' 上悬停成功\n"
                log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                if force_action:
                    log += f"  - 强制操作: 是（忽略可见性检查）\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'scroll':
                await locator.scroll_into_view_if_needed(timeout=timeout_ms)
                execution_time = round(time.time() - start_time, 2)
                log = f"✓ 滚动到元素 '{element_name}' 成功\n"
                log += f"  - 定位器: {locator_strategy}={locator_value}\n"
                log += f"  - 超时设置: {timeout_ms/1000}秒\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'drag':
                target_element_data = self._resolve_drag_target_data(resolved_input_value)
                target_locator = self._build_locator(
                    target_element_data.get('locator_strategy', 'css'),
                    target_element_data.get('locator_value', '')
                )

                await locator.wait_for(state='visible', timeout=timeout_ms)
                await target_locator.wait_for(state='visible', timeout=timeout_ms)
                await locator.scroll_into_view_if_needed(timeout=timeout_ms)
                await target_locator.scroll_into_view_if_needed(timeout=timeout_ms)

                source_box = await locator.bounding_box()
                target_box = await target_locator.bounding_box()
                if not source_box or not target_box:
                    raise ValueError('拖拽时无法获取起点或终点元素坐标')

                source_x = source_box['x'] + source_box['width'] / 2
                source_y = source_box['y'] + source_box['height'] / 2
                target_x = target_box['x'] + target_box['width'] / 2
                target_y = target_box['y'] + target_box['height'] / 2

                await self.page.mouse.move(source_x, source_y)
                await self.page.mouse.down()
                await asyncio.sleep(0.2)
                await self.page.mouse.move(target_x, target_y, steps=20)
                await asyncio.sleep(0.1)
                await self.page.mouse.up()

                execution_time = round(time.time() - start_time, 2)
                log = f"✔ 拖拽元素 '{element_name}' 到 '{target_element_data.get('name', '目标元素')}' 成功\n"
                log += f"  - 起点定位器: {locator_strategy}={locator_value}\n"
                log += f"  - 终点定位器: {target_element_data.get('locator_strategy')}={target_element_data.get('locator_value')}\n"
                log += f"  - 操作方式: mouse.down -> move -> mouse.up\n"
                log += f"  - 执行时间: {execution_time}秒"
                return True, log, None

            elif action_type == 'assert':
                # 根据断言类型执行不同的断言
                if step.assert_type == 'textContains':
                    text = await locator.inner_text(timeout=timeout_ms)
                    if resolved_assert_value in text:
                        log = f"✓ 断言通过: 文本包含 '{resolved_assert_value}'\n"
                        if resolved_assert_value != step.assert_value:
                             log += f"  - 变量解析: '{step.assert_value}' => '{resolved_assert_value}'\n"
                        log += f"  - 实际文本: '{text}'\n"
                        log += f"  - 超时设置: {timeout_ms/1000}秒"
                        return True, log, None
                    else:
                        log = f"✗ 断言失败: 文本不包含 '{resolved_assert_value}'\n"
                        if resolved_assert_value != step.assert_value:
                             log += f"  - 变量解析: '{step.assert_value}' => '{resolved_assert_value}'\n"
                        log += f"  - 实际文本: '{text}'"
                        screenshot = await self.page.screenshot()
                        screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        return False, log, screenshot_base64

                elif step.assert_type == 'textEquals':
                    text = await locator.inner_text(timeout=timeout_ms)
                    if text == resolved_assert_value:
                        log = f"✓ 断言通过: 文本等于 '{resolved_assert_value}'\n"
                        if resolved_assert_value != step.assert_value:
                             log += f"  - 变量解析: '{step.assert_value}' => '{resolved_assert_value}'\n"
                        log += f"  - 超时设置: {timeout_ms/1000}秒"
                        return True, log, None
                    else:
                        log = f"✗ 断言失败: 文本不等于 '{resolved_assert_value}'\n"
                        if resolved_assert_value != step.assert_value:
                             log += f"  - 变量解析: '{step.assert_value}' => '{resolved_assert_value}'\n"
                        log += f"  - 期望: '{resolved_assert_value}'\n"
                        log += f"  - 实际: '{text}'"
                        screenshot = await self.page.screenshot()
                        screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        return False, log, screenshot_base64

                elif step.assert_type == 'isVisible':
                    is_visible = await locator.is_visible()
                    if is_visible:
                        log = f"✓ 断言通过: 元素 '{element_name}' 可见"
                        return True, log, None
                    else:
                        log = f"✗ 断言失败: 元素 '{element_name}' 不可见"
                        screenshot = await self.page.screenshot()
                        screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        return False, log, screenshot_base64

                elif step.assert_type == 'exists':
                    count = await locator.count()
                    if count > 0:
                        log = f"✓ 断言通过: 元素 '{element_name}' 存在"
                        return True, log, None
                    else:
                        log = f"✗ 断言失败: 元素 '{element_name}' 不存在"
                        screenshot = await self.page.screenshot()
                        screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
                        return False, log, screenshot_base64



            else:
                log = f"⚠ 未知的操作类型: {action_type}"
                return True, log, None

        except PlaywrightTimeout as e:
            execution_time = round(time.time() - start_time, 2)
            log = f"✗ 操作超时\n"
            log += f"  - 元素: '{element_name}'\n"
            log += f"  - 定位器: {locator_strategy}={locator_value}\n"
            log += f"  - 超时时间: {execution_time}秒\n"
            log += f"  - 错误: {str(e)}"

            # 捕获失败截图
            try:
                screenshot = await self.page.screenshot()
                screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
            except:
                pass

            return False, log, screenshot_base64

        except Exception as e:
            execution_time = round(time.time() - start_time, 2)
            log = f"✗ 执行失败\n"
            log += f"  - 元素: '{element_name}'\n"
            log += f"  - 定位器: {locator_strategy}={locator_value}\n"
            log += f"  - 执行时间: {execution_time}秒\n"
            log += f"  - 错误: {str(e)}"

            # 捕获失败截图
            try:
                screenshot = await self.page.screenshot()
                screenshot_base64 = f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
            except:
                pass

            return False, log, screenshot_base64

    async def navigate(self, url: str) -> Tuple[bool, str]:
        """
        导航到指定URL

        Args:
            url: 目标URL

        Returns:
            (是否成功, 日志信息)
        """
        try:
            # 检测是否在Linux服务器环境
            import platform
            is_linux = platform.system() == 'Linux'

            # 先等待首屏 DOM 就绪，避免 SPA 的轮询/WebSocket 导致 networkidle 永远等不到
            response = await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)

            load_state_notes = []
            try:
                await self.page.wait_for_load_state('load', timeout=10000)
                load_state_notes.append('load')
            except Exception as load_error:
                load_state_notes.append(f"load未完全稳定: {str(load_error)}")

            try:
                await self.page.wait_for_load_state('networkidle', timeout=5000)
                load_state_notes.append('networkidle')
            except Exception as idle_error:
                load_state_notes.append(f"networkidle未稳定: {str(idle_error)}")

            # 额外等待，确保动态内容加载（Vue/React等SPA应用）
            # 服务器无头模式需要更长的等待时间
            extra_wait = 3 if is_linux else 2
            await asyncio.sleep(extra_wait)

            log = f"✓ 成功导航到: {url}\n"
            if response is not None:
                try:
                    log += f"  - 首次响应状态码: {response.status}\n"
                except Exception:
                    pass
            log += "  - 页面等待策略: domcontentloaded"
            if load_state_notes:
                log += f" -> {'; '.join(load_state_notes)}"
            log += f" + 额外{extra_wait}秒"
            return True, log
        except Exception as e:
            log = f"✗ 导航失败: {url}\n  - 错误: {str(e)}"
            return False, log

    async def capture_screenshot(self) -> str:
        """
        捕获当前页面截图

        Returns:
            截图的base64字符串
        """
        try:
            screenshot = await self.page.screenshot(full_page=True)
            return f"data:image/png;base64,{base64.b64encode(screenshot).decode()}"
        except Exception as e:
            logger.error(f"捕获截图失败: {str(e)}")
            return None
