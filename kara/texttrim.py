TRUNCATED_MARKER = "\n[TRUNCATED: middle omitted]\n"
CUT_MARKER = "\n[TRUNCATED]"


def trim_head_tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= len(TRUNCATED_MARKER):
        return text[:limit]
    budget = limit - len(TRUNCATED_MARKER)
    head_size = int(budget * 0.75)
    tail_size = budget - head_size
    return text[:head_size] + TRUNCATED_MARKER + text[len(text) - tail_size:]


def cut_tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    budget = limit - len(CUT_MARKER)
    if budget <= 0:
        return text[:limit]
    window = text[:budget]
    cut = max(window.rfind("\n"), window.rfind(" "))
    if cut < budget // 2:
        cut = budget
    return window[:cut].rstrip() + CUT_MARKER
