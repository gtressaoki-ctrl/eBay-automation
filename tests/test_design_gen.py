from ebay_automation.design_gen import _wrap_into_lines, keyword_to_phrase


def test_strips_known_suffixes():
    assert keyword_to_phrase("cat mom shirt") == "CAT MOM"
    assert keyword_to_phrase("coffee lover mug") == "COFFEE LOVER"


def test_uppercases_and_collapses_whitespace():
    assert keyword_to_phrase("running   mom shirt") == "RUNNING MOM"


def test_falls_back_to_original_keyword_if_empty_after_strip():
    assert keyword_to_phrase("shirt") == "SHIRT"


def test_wrap_into_lines_never_splits_a_word():
    for phrase in ["CAMPING LIFE", "CAT MOM", "RETIRED AND LOVING IT", "GYM MOTIVATION"]:
        lines = _wrap_into_lines(phrase)
        assert " ".join(lines).split() == phrase.split()


def test_wrap_into_lines_short_phrase_stays_on_one_line():
    assert _wrap_into_lines("CAT MOM") == ["CAT MOM"]


def test_wrap_into_lines_balances_longer_phrase_across_two_lines():
    lines = _wrap_into_lines("RETIRED AND LOVING IT")
    assert len(lines) == 2
    assert all(len(line.split()) >= 1 for line in lines)
