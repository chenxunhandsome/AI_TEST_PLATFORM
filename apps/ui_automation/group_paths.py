def has_group_path_separator(group_path):
    value = str(group_path or '')
    return '/' in value or '\\' in value


def normalize_group_path(group_path):
    if not group_path:
        return []

    if isinstance(group_path, str):
        items = group_path.replace('\\', '/').split('/')
    elif isinstance(group_path, (list, tuple)):
        items = group_path
    else:
        return []

    normalized = []
    for item in items:
        value = str(item or '').strip()
        if value:
            normalized.append(value[:200])
    return normalized
