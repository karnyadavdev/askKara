from datetime import datetime, timedelta, timezone

from kara.prompts import IST, build_system_prompt


def test_system_prompt_states_todays_date_in_ist():
    prompt = build_system_prompt()

    assert "Today's date:" in prompt
    assert "IST" in prompt


def test_date_line_matches_current_ist_date():
    prompt = build_system_prompt()

    ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    assert ist_now.strftime("%A") in prompt
    assert str(ist_now.year) in prompt


def test_ist_offset_is_fixed_five_thirty():
    assert IST.utcoffset(None) == timedelta(hours=5, minutes=30)


def test_date_line_sits_after_the_intro_not_inside_tool_policy():
    prompt = build_system_prompt()

    assert prompt.index("Today's date:") < prompt.index("Available tools:")


def test_source_playbook_section_exists_between_tools_and_policy():
    prompt = build_system_prompt()

    assert "Source playbook" in prompt
    assert prompt.index("Source playbook") > prompt.index("Available tools:")
    assert prompt.index("Source playbook") < prompt.index("Tool policy:")


def test_playbook_lists_every_verified_source():
    prompt = build_system_prompt()

    for site in (
        "amazon.com",
        "flipkart.com",
        "stackoverflow.com",
        "medium.com",
        "quora.com",
        "youtube.com",
        "news.ycombinator.com",
        "linkedin.com/company",
        "reddit.com",
        "x.com",
        "instagram.com",
    ):
        assert site in prompt, site


def test_playbook_forbids_prices_from_search_snippets():
    prompt = build_system_prompt()

    assert "Never take a price from a web_search snippet" in prompt


def test_playbook_teaches_site_operator_for_single_site_questions():
    prompt = build_system_prompt()

    assert "site:example.com" in prompt


def test_playbook_is_present_in_deep_mode_too():
    prompt = build_system_prompt(max_sources=35)

    assert "Source playbook" in prompt
    assert "amazon.com" in prompt

