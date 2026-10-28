import re

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


def _decide(tag: Tag) -> str | None:
    if tag.name in PROTECTED_TAGS:
        return None
    action: str | None = None
    if tag.name == "nav":
        action = "delete"
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
    if action == "delete":
        if tag.find(PROTECTED_TAGS):
            return None
        if len(_collapse(tag.get_text(" ", strip=True))) >= JUNK_TEXT_LIMIT:
            return "move"
    return action


def _render_table(table: Tag) -> str:
    rows: list[str] = []
    for row in table.find_all("tr"):
        cells = [
            _collapse(cell.get_text(" ", strip=True))
            for cell in row.find_all(("td", "th"), recursive=False)
        ]
        if cells:
            rows.append(" | ".join(cells))
    if not rows:
        return _collapse(table.get_text(" ", strip=True))
    return "\n".join(rows)


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


def page_to_text(html: str) -> str:
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

    deleted: set[int] = set()
    for tag in list(soup.find_all(True)):
        if tag.parent is None or tag.name in ("html", "body"):
            continue
        if any(id(parent) in deleted for parent in tag.parents):
            continue
        if _decide(tag) == "delete":
            deleted.add(id(tag))
            tag.decompose()

    moved: list[Tag] = []
    for tag in list(soup.find_all(True)):
        if tag.parent is None or tag.name in ("html", "body"):
            continue
        if any(id(parent) in deleted for parent in tag.parents):
            continue
        if _decide(tag) == "move":
            deleted.add(id(tag))
            moved.append(tag.extract())

    parts = [rendered_first, _render(soup.body or soup)]
    parts.extend(_render(tag) for tag in moved)
    return "\n\n".join(part for part in parts if part).strip()
