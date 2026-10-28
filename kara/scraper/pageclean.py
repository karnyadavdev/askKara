import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

DROP_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
    "template",
    "iframe",
    "canvas",
    "object",
    "embed",
)
PROTECTED_TAGS = ("table", "pre", "code", "blockquote")
DELETE_SUBSTRING = (
    "advert",
    "adsbygoogle",
    "adsense",
    "adslot",
    "adunit",
    "sponsored",
    "cookie-banner",
    "cookiebanner",
    "cookie-notice",
    "cookienotice",
    "cookie-consent",
    "cookieconsent",
    "cookie-policy",
    "cookiepolicy",
    "cookie-bar",
    "cookiebar",
    "cookie-popup",
    "cookie-modal",
    "cookie-wall",
    "cookie-alert",
    "cookiealert",
    "cookie-law",
    "cookielaw",
    "cookiebox",
    "consent-banner",
    "consentbanner",
    "consent-modal",
    "consentmodal",
    "consent-popup",
    "consent-overlay",
    "consent-manager",
    "consentmanager",
    "onetrust",
    "osano",
    "cookiebot",
    "cc-window",
    "navbar",
    "subnav",
    "topnav",
)
DELETE_WORDS = ("ad", "ads", "nav")
MOVE_SUBSTRING = (
    "footer",
    "sidebar",
    "aside",
    "complementary",
    "navigation",
    "breadcrumb",
    "pagin",
    "pager",
    "comments",
    "related",
    "recommend",
    "trending",
    "popular",
    "sharing",
    "social",
    "facebook",
    "twitter",
    "linkedin",
    "instagram",
    "pinterest",
    "whatsapp",
    "tiktok",
    "newsletter",
    "subscription",
    "signup",
    "mailing",
    "popup",
    "modal",
    "overlay",
    "interstitial",
    "lightbox",
    "toast",
    "cookie",
    "consent",
)
MOVE_WORDS = ("comment", "share", "subscribe")
MOVE_TAGS = ("footer", "aside")
BLOCK_TAGS = (
    "p",
    "div",
    "section",
    "article",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "figure",
    "figcaption",
    "details",
    "summary",
    "header",
    "footer",
    "main",
    "address",
    "fieldset",
    "form",
    "hr",
    "tbody",
    "thead",
    "tfoot",
    "tr",
    "caption",
    "dialog",
    "label",
)
JUNK_TEXT_LIMIT = 400
NAV_LINK_LIMIT = 12
EXTRAS_LIMIT = 1500
CORE_TEXT_SHARE = 0.4
CORE_TEXT_MIN = 200
CORE_TAGS = ("html", "body", "main", "article")
CTA_TEXT_LIMIT = 80
CTA_TEXT = (
    "sign up",
    "signup",
    "register",
    "create account",
    "join our",
    "subscribe",
    "newsletter",
    "log in",
    "login",
    "sign in",
    "follow us",
    "enable notification",
    "accept all",
    "manage preference",
    "do not sell",
    "cookie settings",
    "get the app",
    "download our",
    "book now",
    "buy now",
    "shop now",
    "add to cart",
)
_CONTENT_ANCESTORS = ("main", "article")
_SENTINEL = "\ue000{}\ue001"
_SPACE_RE = re.compile(r"[^\S\n]+")
_BLANK_RE = re.compile(r"\n{3,}")
_WS_RE = re.compile(r"\s+")


def _collapse(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _words(name: str) -> set[str]:
    return {word for word in re.split(r"[^a-z0-9]+", name) if word}


def _matches(name: str, substrings: tuple[str, ...], word_patterns: tuple[str, ...]) -> bool:
    lowered = name.casefold()
    if any(pattern in lowered for pattern in substrings):
        return True
    tokens = _words(lowered)
    return any(pattern in tokens for pattern in word_patterns)


def _tag_names(tag: Tag) -> list[str]:
    names: list[str] = []
    classes = tag.get("class")
    if classes:
        names.append(" ".join(classes) if isinstance(classes, list) else str(classes))
    for attr in ("id", "role", "aria-label"):
        value = tag.get(attr)
        if value:
            names.append(str(value))
    return names


CTA_TAGS = ("a", "button")


def _is_junk_cta(tag: Tag) -> bool:
    if tag.name not in CTA_TAGS:
        return False
    text = _collapse(tag.get_text(" ", strip=True)).casefold()
    if not text or len(text) > CTA_TEXT_LIMIT:
        return False
    if not any(pattern in text for pattern in CTA_TEXT):
        return False
    for parent in tag.parents:
        if parent.name in _CONTENT_ANCESTORS:
            return False
    return True


def _text_len(tag: Tag) -> int:
    return len(_collapse(tag.get_text(" ", strip=True)))


def _core_ids(soup: BeautifulSoup) -> set[int]:
    core = {id(tag) for tag in soup.find_all(CORE_TAGS)}
    for heading in soup.find_all("h1"):
        if heading.find_parent(("nav", "header", "footer", "aside")):
            continue
        core.update(id(parent) for parent in heading.parents)
    return core


def _decide(tag: Tag, total_chars: int, core_ids: set[int]) -> str | None:
    if tag.name in PROTECTED_TAGS:
        return None
    action: str | None = None
    if tag.name == "nav":
        action = "move"
    elif tag.name in MOVE_TAGS:
        action = "move"
    else:
        for name in _tag_names(tag):
            if _matches(name, DELETE_SUBSTRING, DELETE_WORDS):
                action = "delete"
                break
            if _matches(name, MOVE_SUBSTRING, MOVE_WORDS):
                action = "move"
                break
    if action is None and _is_junk_cta(tag):
        action = "move"
    if action is None:
        return None
    if id(tag) in core_ids:
        return None
    span = _text_len(tag)
    if action == "delete":
        if tag.find(PROTECTED_TAGS):
            return None
        if _is_nav_like(tag):
            return "move"
        if span >= JUNK_TEXT_LIMIT:
            return "move"
        return "delete"
    if span >= CORE_TEXT_MIN and span > total_chars * CORE_TEXT_SHARE:
        return None
    return "move"


def _span_value(cell: Tag, attr: str) -> int:
    raw = cell.get(attr)
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 100))


def _render_table(table: Tag) -> str:
    occupied: dict[tuple[int, int], str] = {}
    col_count = 0
    for r, row in enumerate(table.find_all("tr")):
        c = 0
        for cell in row.find_all(("td", "th"), recursive=False):
            while (r, c) in occupied:
                c += 1
            text = _collapse(cell.get_text(" ", strip=True))
            colspan = _span_value(cell, "colspan")
            rowspan = _span_value(cell, "rowspan")
            for dr in range(rowspan):
                for dc in range(colspan):
                    occupied[(r + dr, c + dc)] = text
            col_count = max(col_count, c + colspan)
            c += colspan
    if not occupied:
        return _collapse(table.get_text(" ", strip=True))
    max_row = max(r for (r, _) in occupied)
    lines = []
    for r in range(max_row + 1):
        if not any((r, c) in occupied for c in range(col_count)):
            continue
        lines.append(" | ".join(occupied.get((r, c), "") for c in range(col_count)))
    return "\n".join(lines)


def _resolve_href(href, base_url: str | None) -> str:
    if not href:
        return ""
    value = str(href).strip()
    if not value or value.startswith("#"):
        return ""
    lowered = value.casefold()
    if lowered.startswith(("javascript:", "data:")):
        return ""
    if base_url:
        return urljoin(base_url, value)
    return value


def _is_nav_like(tag: Tag) -> bool:
    if tag.name == "nav":
        return True
    for name in _tag_names(tag):
        if "nav" in _words(name) or "navigation" in name.casefold():
            return True
    return False


def _render_nav(nav: Tag, base_url: str | None, limit: int = NAV_LINK_LIMIT) -> tuple[str, int]:
    lines: list[str] = []
    skipped = 0
    for link in nav.find_all("a"):
        text = _collapse(link.get_text(" ", strip=True))
        href = _resolve_href(link.get("href"), base_url)
        label = ""
        if text and href:
            label = f"- {text} ({href})"
        elif text:
            label = f"- {text}"
        elif href:
            label = f"- {href}"
        if not label:
            continue
        if len(lines) >= limit:
            skipped += 1
            continue
        lines.append(label)
    if not lines and not skipped:
        return _render(nav), 0
    used = len(lines)
    if skipped:
        lines.append(f"[+{skipped} nav links omitted]")
    return "[nav links]\n" + "\n".join(lines), used


def _cap_extras(text: str) -> str:
    if len(text) <= EXTRAS_LIMIT:
        return text
    window = text[:EXTRAS_LIMIT]
    cut = max(window.rfind("\n"), window.rfind(" "))
    if cut < EXTRAS_LIMIT // 2:
        cut = EXTRAS_LIMIT
    omitted = len(text) - cut
    return window[:cut].rstrip() + f"\n[+{omitted} chars omitted]"


def _render(root: Tag) -> str:
    if root is None:
        return ""
    placeholders: dict[str, str] = {}

    def store(text: str) -> str:
        key = _SENTINEL.format(len(placeholders))
        placeholders[key] = text
        return key

    for table in reversed(list(root.find_all("table"))):
        if table.parent is None:
            continue
        table.replace_with(store(_render_table(table)))

    for pre in list(root.find_all("pre")):
        if pre.parent is None:
            continue
        pre.replace_with(store(pre.get_text("").strip("\n")))

    for image in list(root.find_all("img")):
        alt = _collapse(image.get("alt") or "")
        if alt:
            image.replace_with(store(f"[image: {alt}]"))
        else:
            image.decompose()

    for tag in root.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")

    for br in root.find_all("br"):
        br.replace_with("\n")

    text = root.get_text("")
    lines = [_SPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = _BLANK_RE.sub("\n\n", "\n".join(lines)).strip()
    for key, value in reversed(list(placeholders.items())):
        text = text.replace(key, value)
    return text.strip()


def page_to_text(html: str, base_url: str | None = None) -> str:
    if not html:
        return ""
    html = html.replace("\ue000", "").replace("\ue001", "")
    soup = BeautifulSoup(html, "lxml")

    rendered_first = ""
    node = soup.select_one("[data-yada-rendered-text]")
    if node is not None:
        rendered_first = _collapse(node.get_text(" ", strip=True))
        node.decompose()

    for tag in soup.find_all(DROP_TAGS):
        tag.decompose()

    total_chars = _text_len(soup.body or soup)
    core_ids = _core_ids(soup)

    deleted: set[int] = set()
    for tag in list(soup.find_all(True)):
        if tag.parent is None or tag.name in ("html", "body"):
            continue
        if any(id(parent) in deleted for parent in tag.parents):
            continue
        if _decide(tag, total_chars, core_ids) == "delete":
            deleted.add(id(tag))
            tag.decompose()

    moved: list[Tag] = []
    for tag in list(soup.find_all(True)):
        if tag.parent is None or tag.name in ("html", "body"):
            continue
        if any(id(parent) in deleted for parent in tag.parents):
            continue
        if _decide(tag, total_chars, core_ids) == "move":
            deleted.add(id(tag))
            moved.append(tag.extract())

    parts = [rendered_first, _render(soup.body or soup)]
    extras: list[str] = []
    nav_left = NAV_LINK_LIMIT
    for tag in moved:
        if _is_nav_like(tag):
            block, used = _render_nav(tag, base_url, nav_left)
            nav_left -= used
        else:
            block = _render(tag)
        if block:
            extras.append(block)
    if extras:
        parts.append("[page extras]\n" + _cap_extras("\n\n".join(extras)))
    return "\n\n".join(part for part in parts if part).strip()
