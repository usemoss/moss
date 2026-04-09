from moss_cli.commands.search import _parse_set_command


def test_parse_set_alpha_valid() -> None:
    parsed, err = _parse_set_command("/set alpha 0.5")
    assert err is None
    assert parsed == "alpha=0.5"


def test_parse_set_top_k_valid_dash_name() -> None:
    parsed, err = _parse_set_command("/set top-k 12")
    assert err is None
    assert parsed == "top_k=12"


def test_parse_set_top_k_valid_compact_name() -> None:
    parsed, err = _parse_set_command("/set topk 4")
    assert err is None
    assert parsed == "top_k=4"


def test_parse_set_usage_error_for_wrong_arity() -> None:
    parsed, err = _parse_set_command("/set alpha")
    assert parsed is None
    assert err == "Usage: /set <alpha|top-k> <value>"


def test_parse_set_unknown_key_error() -> None:
    parsed, err = _parse_set_command("/set beta 0.2")
    assert parsed is None
    assert err == "Unknown setting. Supported: alpha, top-k"


def test_parse_set_alpha_non_numeric_error() -> None:
    parsed, err = _parse_set_command("/set alpha abc")
    assert parsed is None
    assert err == "Invalid alpha. Must be a number between 0.0 and 1.0."


def test_parse_set_alpha_out_of_range_error() -> None:
    parsed, err = _parse_set_command("/set alpha 1.2")
    assert parsed is None
    assert err == "Invalid alpha. Must be between 0.0 and 1.0."


def test_parse_set_top_k_non_numeric_error() -> None:
    parsed, err = _parse_set_command("/set top-k abc")
    assert parsed is None
    assert err == "Invalid top-k. Must be a positive integer."


def test_parse_set_top_k_non_positive_error() -> None:
    parsed, err = _parse_set_command("/set top-k 0")
    assert parsed is None
    assert err == "Invalid top-k. Must be >= 1."
