from kara.config import Settings
from kara.scraper.pageclean import page_to_text
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


def test_extract_payload_prefers_cleaned_html_over_text():
    title, text = extract_payload(
        {"content": {"html": "<title>X</title><p>from html</p>", "markdown": "clean text"}}
    )

    assert title == "X"
    assert "from html" in text
    assert "clean text" not in text


def test_extract_payload_falls_back_to_text_without_html():
    title, text = extract_payload({"content": {"markdown": "clean   text"}})

    assert title == ""
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


def test_cleaner_empty_input():
    assert page_to_text("") == ""


def test_cleaner_drops_labelled_junk_and_demotes_nav():
    html = (
        "<body><nav>nav junk</nav>"
        '<div class="ad-slot">buy now</div>'
        '<div id="cookie-banner">we use cookies</div>'
        "<p>real content</p></body>"
    )
    text = page_to_text(html)

    assert "real content" in text
    assert "nav junk" in text
    assert text.index("real content") < text.index("nav junk")
    assert "buy now" not in text
    assert "we use cookies" not in text


def test_cleaner_keeps_structure_tables_and_code():
    html = (
        "<body><h1>Title</h1><p>First para</p><p>Second<br>line</p>"
        "<pre>def f():\n    return 1</pre>"
        "<table><tr><th>A</th><th>B</th></tr>"
        "<tr><td>1</td><td>2</td></tr></table></body>"
    )
    text = page_to_text(html)

    assert "Title" in text
    assert "First para" in text
    assert "Second\nline" in text
    assert "def f():\n    return 1" in text
    assert "A | B" in text
    assert "1 | 2" in text


def test_cleaner_moves_footer_to_end():
    html = "<body><p>MAIN</p><footer><p>FOOTNOTE</p></footer></body>"
    text = page_to_text(html)

    assert "MAIN" in text
    assert "FOOTNOTE" in text
    assert text.index("MAIN") < text.index("FOOTNOTE")


def test_cleaner_rescues_protected_content_in_junk_block():
    html = (
        '<body><div class="ad-slot">'
        "<table><tr><td>REAL DATA</td></tr></table>"
        "</div><p>body text</p></body>"
    )
    text = page_to_text(html)

    assert "REAL DATA" in text
    assert "body text" in text


def test_cleaner_moves_long_junk_text_instead_of_deleting():
    long_text = "IMPORTANT " * 50
    filler = "".join(
        f"<p>filler paragraph {i} with enough words to keep the junk share low</p>"
        for i in range(20)
    )
    html = f'<body><p>main</p>{filler}<div class="advertisement">{long_text}</div></body>'
    text = page_to_text(html)

    assert "IMPORTANT" in text
    assert text.index("filler paragraph 19") < text.index("IMPORTANT")


def test_cleaner_word_matching_avoids_false_positives():
    html = (
        "<body><p>alpha</p>"
        '<div class="reader-mode">keep reader</div>'
        '<div class="navy-theme">keep navy</div>'
        '<div class="ad-unit">drop ad</div></body>'
    )
    text = page_to_text(html)

    assert "keep reader" in text
    assert "keep navy" in text
    assert "drop ad" not in text


def test_cleaner_rendered_text_div_comes_first_and_once():
    html = (
        "<body><p>main body</p>"
        '<div data-yada-rendered-text="true" style="display:none">'
        "RENDERED TEXT BLOB</div></body>"
    )
    text = page_to_text(html)

    assert text.startswith("RENDERED TEXT BLOB")
    assert text.count("RENDERED TEXT BLOB") == 1
    assert "main body" in text


def test_cleaner_moves_comments_but_keeps_them():
    html = '<body><p>MAIN</p><div class="comments"><p>first comment here</p></div></body>'
    text = page_to_text(html)

    assert "first comment here" in text
    assert text.index("MAIN") < text.index("first comment here")


def test_cleaner_removes_embedded_junk_tags():
    html = '<body><svg><text>vec</text></svg><p>text</p><iframe src="x"></iframe></body>'
    text = page_to_text(html)

    assert "text" in text
    assert "vec" not in text


def test_cleaner_never_drops_content_in_colliding_labels():
    html = (
        "<body>"
        '<div class="cookie-recipe"><p>melt the butter and sugar</p></div>'
        '<div class="consent-form"><p>patient signed the consent form</p></div>'
        '<div class="subscriber-count"><p>1,204,553 subscribers</p></div>'
        '<div class="twitter-trends"><p>top trend: KUWTK finale</p></div>'
        '<div class="shareholders-report"><p>EPS grew 12 percent</p></div>'
        '<div class="modal-content"><p>quick view price 499</p></div>'
        '<div class="navigation-guide"><p>use the stars to find north</p></div>'
        '<div class="pagination-lesson"><p>page size matters</p></div>'
        '<div class="breadcrumb-topping"><p>crumbs for the topping</p></div>'
        "<p>main article body</p>"
        "</body>"
    )
    text = page_to_text(html)

    for phrase in (
        "melt the butter and sugar",
        "patient signed the consent form",
        "1,204,553 subscribers",
        "top trend: KUWTK finale",
        "EPS grew 12 percent",
        "quick view price 499",
        "use the stars to find north",
        "page size matters",
        "crumbs for the topping",
        "main article body",
    ):
        assert phrase in text


def test_cleaner_nested_tables_render_once():
    html = (
        "<body><table id='wrap'>"
        "<tr><td>Header cell</td></tr>"
        "<tr><td><table id='inner'>"
        "<tr><td>row one content</td></tr>"
        "<tr><td>row two content</td></tr>"
        "</table></td></tr>"
        "</table></body>"
    )
    text = page_to_text(html)

    assert text.count("Header cell") == 1
    assert text.count("row one content") == 1
    assert text.count("row two content") == 1
    assert text.index("Header cell") < text.index("row one content")


def test_cleaner_strips_sentinel_chars_from_input():
    html = "<body><p>before \ue000fake\ue001 marker</p><table><tr><td>cell text</td></tr></table></body>"
    text = page_to_text(html)

    assert "\ue000" not in text
    assert "\ue001" not in text
    assert "before fake marker" in text
    assert "cell text" in text


def test_cleaner_pre_inside_table_keeps_code_content():
    html = (
        "<body><table><tr><td><pre>line one\n  line two</pre></td>"
        "<td>other cell</td></tr></table></body>"
    )
    text = page_to_text(html)

    assert "line one" in text
    assert "line two" in text
    assert "other cell" in text


def test_cleaner_demotes_bare_header_cta_link():
    html = (
        "<body><header><a href='/login'>Log in</a> "
        "<a href='/signup'>Sign up for our newsletter</a></header>"
        "<main><h1>Real Title</h1><p>the body copy</p></main></body>"
    )
    text = page_to_text(html)

    assert "Real Title" in text
    assert "the body copy" in text
    assert "Sign up for our newsletter" in text
    assert text.index("the body copy") < text.index("Sign up for our newsletter")


def test_cleaner_keeps_inline_cta_link_inside_article():
    html = (
        "<body><article><p>You can <a href='/signup'>sign up</a> "
        "for the workshop any time.</p><p>more detail</p></article></body>"
    )
    text = page_to_text(html)

    assert "sign up" in text
    assert "for the workshop any time" in text
    assert text.index("sign up") < text.index("more detail")


def test_cleaner_expands_rowspan_under_right_header():
    html = (
        "<body><table>"
        "<tr><th>Store</th><th>Price</th><th>Stock</th></tr>"
        '<tr><td rowspan="2">Acme</td><td>499</td><td>In stock</td></tr>'
        "<tr><td>479</td><td>3 left</td></tr>"
        "</table></body>"
    )
    text = page_to_text(html)

    assert "Store | Price | Stock" in text
    assert "Acme | 499 | In stock" in text
    assert "Acme | 479 | 3 left" in text


def test_cleaner_expands_colspan_across_columns():
    html = (
        "<body><table>"
        '<tr><th colspan="2">Product</th><th>Price</th></tr>'
        "<tr><td>A</td><td>B</td><td>10</td></tr>"
        "</table></body>"
    )
    text = page_to_text(html)

    assert "Product | Product | Price" in text
    assert "A | B | 10" in text


def test_cleaner_ignores_garbage_span_values():
    html = (
        "<body><table>"
        '<tr><td colspan="abc" rowspan="-3">x</td><td>y</td></tr>'
        "</table></body>"
    )
    text = page_to_text(html)

    assert "x | y" in text


def test_cleaner_keeps_wrapper_with_junk_class_in_place():
    wrapped = "WRAPPED ARTICLE " * 20
    trailing = "TRAILING NOTE " * 8
    html = (
        f'<body><div class="content-with-sidebar"><p>{wrapped}</p></div>'
        f"<p>{trailing}</p></body>"
    )
    text = page_to_text(html)

    assert "WRAPPED ARTICLE" in text
    assert text.index("WRAPPED ARTICLE") < text.index("TRAILING NOTE")


def test_cleaner_keeps_big_move_match_in_place():
    body = "ARTICLE BODY TEXT " * 60
    html = f'<body><div class="sidebar">{body}</div><p>short tail</p></body>'
    text = page_to_text(html)

    assert "ARTICLE BODY TEXT" in text
    assert text.index("ARTICLE BODY TEXT") < text.index("short tail")


def test_cleaner_keeps_h1_ancestors_in_place():
    html = (
        '<body><div class="related-posts"><h1>Real Headline</h1>'
        "<p>the story</p></div><p>tail note</p></body>"
    )
    text = page_to_text(html)

    assert text.index("Real Headline") < text.index("tail note")


def test_cleaner_does_not_protect_h1_inside_site_chrome():
    links = "".join(f'<a href="/t{i}">tutorial {i}</a>' for i in range(8))
    html = (
        "<body>"
        f'<nav id="top-nav-bar"><h1>Site</h1><div>{links}</div></nav>'
        "<main><h1>Real Title</h1><p>the body copy</p></main></body>"
    )
    text = page_to_text(html)

    assert text.index("the body copy") < text.index("tutorial 0")
    assert text.index("Real Title") < text.index("tutorial 0")


def test_cleaner_treats_div_nav_as_link_index():
    links = "".join(f'<a href="/t{i}">tutorial {i}</a>' for i in range(14))
    html = (
        f'<body><div id="top-nav-bar">{links}</div>'
        "<main><h1>Real Title</h1><p>the body copy</p></main></body>"
    )
    text = page_to_text(html)

    assert text.index("the body copy") < text.index("tutorial 0")
    assert "tutorial 11" in text
    assert "tutorial 12" not in text


def test_cleaner_keeps_main_and_article_tags():
    html = (
        '<body><main class="ad-slot"><p>MAIN BODY</p></main>'
        '<article class="newsletter"><p>ARTICLE BODY</p></article></body>'
    )
    text = page_to_text(html)

    assert "MAIN BODY" in text
    assert "ARTICLE BODY" in text


def test_cleaner_turns_nav_into_link_index():
    html = (
        "<body><p>ARTICLE BODY</p><nav>"
        '<a href="/page2">Next page</a>'
        '<a href="/report.pdf">Download PDF</a>'
        "</nav></body>"
    )
    text = page_to_text(html, base_url="https://example.com/news/story")

    assert "ARTICLE BODY" in text
    assert "Next page (https://example.com/page2)" in text
    assert "Download PDF (https://example.com/report.pdf)" in text
    assert text.index("ARTICLE BODY") < text.index("Next page")


def test_cleaner_caps_nav_links():
    links = "".join(f'<a href="/p{i}">link {i}</a>' for i in range(20))
    html = f"<body><p>ARTICLE BODY</p><nav>{links}</nav></body>"
    text = page_to_text(html)

    assert "link 0" in text
    assert "link 11" in text
    assert "link 12" not in text
    assert "[+8 nav links omitted]" in text


def test_cleaner_caps_and_labels_extras():
    filler = "".join(
        f"<p>main paragraph {i} with a reasonable amount of text for the page</p>"
        for i in range(100)
    )
    junk = "RELATED ITEM " * 200
    html = f'<body>{filler}<footer><p>{junk}</p></footer></body>'
    text = page_to_text(html)

    assert "[page extras]" in text
    assert "RELATED ITEM" in text
    assert "[+" in text
    assert "chars omitted]" in text


def test_cleaner_nav_links_survive_large_extras():
    filler = "".join(
        f"<p>main paragraph {i} with enough words for the page</p>" for i in range(100)
    )
    nav = "".join(f'<a href="/n{i}">nav {i}</a>' for i in range(12))
    sidebar = "SIDEBAR TEXT " * 230
    html = f"<body>{filler}<nav>{nav}</nav><aside><p>{sidebar}</p></aside></body>"
    text = page_to_text(html)

    assert "nav 0" in text
    assert "nav 11" in text
    assert "SIDEBAR TEXT" in text
    assert "[+" in text


def test_cleaner_keeps_image_alt_text():
    html = (
        "<body><p>before</p>"
        '<img src="chart.png" alt="Revenue rose 40 percent in 2025">'
        "<p>after</p></body>"
    )
    text = page_to_text(html)

    assert text.index("before") < text.index("Revenue rose 40 percent in 2025")
    assert text.index("Revenue rose 40 percent in 2025") < text.index("after")


def test_extract_payload_adds_page_info_header_from_jsonld():
    html = (
        "<html><head><script type='application/ld+json'>"
        '{"datePublished":"2026-03-15","author":{"name":"Jane Doe"}}'
        "</script></head><body><p>Article body</p></body></html>"
    )
    title, text = extract_payload({"content": {"html": html}})

    assert text.startswith("[page info: published 2026-03-15 | author Jane Doe]")


def test_extract_payload_reads_meta_and_time():
    html = (
        "<html><head>"
        '<meta property="article:published_time" content="2026-01-02T10:00:00Z">'
        '<meta name="author" content="Sam Lee">'
        "</head><body><p>Article body</p></body></html>"
    )
    title, text = extract_payload({"content": {"html": html}})

    assert "published 2026-01-02T10:00:00Z" in text
    assert "author Sam Lee" in text


def test_extract_payload_omits_page_info_without_metadata():
    title, text = extract_payload(
        {"content": {"html": "<html><body><p>plain</p></body></html>"}}
    )

    assert text == "plain"


def test_extract_payload_resolves_nav_links_against_result_url():
    html = "<body><p>body</p><nav><a href='/next'>Next</a></nav></body>"
    title, text = extract_payload(
        {"content": {"html": html}, "url": "https://example.com/a/b"}
    )

    assert "https://example.com/next" in text


def test_extract_payload_prefers_jsonld_node_matching_page_url():
    html = (
        "<html><head><script type='application/ld+json'>"
        '{"@graph":['
        '{"@type":"NewsArticle","url":"https://example.com/other",'
        '"datePublished":"2020-01-01","author":"Wrong"},'
        '{"@type":"NewsArticle","url":"https://example.com/story",'
        '"datePublished":"2026-05-05","author":"Right"}'
        "]}"
        "</script></head><body><p>body</p></body></html>"
    )
    title, text = extract_payload(
        {"content": {"html": html}, "url": "https://example.com/story"}
    )

    assert "published 2026-05-05" in text
    assert "author Right" in text
