DEFAULT_BROWSER_WIDTH = 1920
DEFAULT_BROWSER_HEIGHT = 1060
MIN_BROWSER_WIDTH = 320
MIN_BROWSER_HEIGHT = 240
MAX_BROWSER_WIDTH = 7680
MAX_BROWSER_HEIGHT = 4320


def normalize_browser_dimension(value, default_value, *, minimum, maximum):
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return default_value

    if normalized < minimum or normalized > maximum:
        return default_value
    return normalized


def resolve_browser_resolution(project=None, browser_width=None, browser_height=None):
    if project is not None:
        if browser_width is None:
            browser_width = getattr(project, 'browser_width', None)
        if browser_height is None:
            browser_height = getattr(project, 'browser_height', None)

    width = normalize_browser_dimension(
        browser_width,
        DEFAULT_BROWSER_WIDTH,
        minimum=MIN_BROWSER_WIDTH,
        maximum=MAX_BROWSER_WIDTH,
    )
    height = normalize_browser_dimension(
        browser_height,
        DEFAULT_BROWSER_HEIGHT,
        minimum=MIN_BROWSER_HEIGHT,
        maximum=MAX_BROWSER_HEIGHT,
    )
    return width, height


def get_default_browser_resolution_label():
    return f'{DEFAULT_BROWSER_WIDTH}x{DEFAULT_BROWSER_HEIGHT}'


def get_browser_resolution_label(project=None, browser_width=None, browser_height=None):
    width, height = resolve_browser_resolution(
        project=project,
        browser_width=browser_width,
        browser_height=browser_height,
    )
    return f'{width}x{height}'


def get_default_chromium_window_size_argument():
    return get_chromium_window_size_argument()


def get_chromium_window_size_argument(project=None, browser_width=None, browser_height=None):
    width, height = resolve_browser_resolution(
        project=project,
        browser_width=browser_width,
        browser_height=browser_height,
    )
    return f'--window-size={width},{height}'
