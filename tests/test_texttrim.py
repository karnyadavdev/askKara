from kara.texttrim import CUT_MARKER, TRUNCATED_MARKER, cut_tail, trim_head_tail


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


def test_cut_tail_short_text_untouched():
    text = "hello world"
    assert cut_tail(text, 100) == text


def test_cut_tail_hits_limit_exactly():
    text = "a" * 1000
    result = cut_tail(text, 500)
    assert len(result) == 500
    assert result.endswith(CUT_MARKER)


def test_cut_tail_prefers_sentence_boundary():
    text = ("word " * 300) + ". Next sentence here " + ("filler " * 300)
    result = cut_tail(text, 900)
    assert len(result) <= 900
    assert result.endswith(CUT_MARKER)
    assert "Next sentence here" not in result


def test_cut_tail_hard_cuts_when_no_boundary():
    text = "x" * 2000
    result = cut_tail(text, 100)
    assert len(result) == 100
    assert result.endswith(CUT_MARKER)
