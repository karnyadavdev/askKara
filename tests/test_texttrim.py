from kara.texttrim import TRUNCATED_MARKER, trim_head_tail


def test_short_text_untouched():
    text = "hello world"
    assert trim_head_tail(text, 100) == text


def test_exact_limit_untouched():
    text = "x" * 50
    assert trim_head_tail(text, 50) == text


def test_long_text_hits_limit_exactly():
    text = "a" * 1000 + "MIDDLE" + "z" * 1000
    result = trim_head_tail(text, 500)
    assert len(result) == 500
    assert TRUNCATED_MARKER in result


def test_head_and_tail_survive():
    text = "HEAD" + "m" * 4000 + "TAIL"
    result = trim_head_tail(text, 1000)
    assert result.startswith("HEAD")
    assert result.endswith("TAIL")
    head, tail = result.split(TRUNCATED_MARKER)
    assert "m" * 100 in head
    assert "m" * 100 in tail
