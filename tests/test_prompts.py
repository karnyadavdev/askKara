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
