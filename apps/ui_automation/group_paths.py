import re


GROUP_PATH_SPLIT_RE = re.compile(r'\s*(?:/|\\|>|＞|／|->|→)\s*')
GROUP_PATH_SEPARATOR_RE = re.compile(r'(?:/|\\|>|＞|／|->|→)')


def normalize_group_path(raw_group_path):
    """Normalize group path input into clean hierarchical segments."""
    if isinstance(raw_group_path, str):
        candidates = [raw_group_path]
    elif isinstance(raw_group_path, (list, tuple)):
        candidates = list(raw_group_path)
    else:
        return []

    segments = []
    for item in candidates:
        text = str(item or '').strip()
        if not text:
            continue
        for segment in GROUP_PATH_SPLIT_RE.split(text):
            normalized = segment.strip()
            if normalized:
                segments.append(normalized)
    return segments


def has_group_path_separator(name):
    return bool(GROUP_PATH_SEPARATOR_RE.search(str(name or '')))
