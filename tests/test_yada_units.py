from kara.config import Settings
from kara.scraper.yada import YadaClient, extract_payload, html_to_text


def test_extract_payload_from_html():
    html = (
        "<html><head><title> My Page </title></head>"
        "<body><p>Hello world content</p><script>evil()</script></body></html>"
    )
    title, text = extract_payload({"content": {"html": html}})

    assert title == "My Page"
    assert "Hello world content" in text
    assert "evil" not in text


def test_extract_payload_prefers_markdown_text():
    title, text = extract_payload({"content": {"html": "<title>X</title>", "markdown": "clean text"}})

    assert title == "X"
    assert text == "clean text"


def test_extract_payload_handles_string_content():
    title, text = extract_payload({"content": "<p>fragment body</p>"})

    assert "fragment body" in text


def test_html_to_text_strips_scripts_and_styles():
    text = html_to_text("<style>body{color:red}</style><p>keep</p><script>drop()</script>")

    assert "keep" in text
    assert "drop" not in text
    assert "color:red" not in text


async def test_mode_off_returns_failure():
    client = YadaClient(Settings(yada_mode="off"))

    result = await client.scrape("https://example.com")

    assert result["ok"] is False
    assert "disabled" in result["error"]


async def test_import_mode_without_root_returns_failure():
    client = YadaClient(Settings(yada_mode="import", yada_root=""))

    result = await client.scrape("https://example.com")

    assert result["ok"] is False
    assert "YADA_ROOT" in result["error"]
