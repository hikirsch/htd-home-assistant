def _reduce_whitelist(user_input, source_count):
    """Replicate whitelist reduction from async_step_zone_source_filter."""
    whitelist = [
        i for i in range(1, source_count + 1)
        if user_input.get(f"source_{i}_enabled", True)
    ]
    if not whitelist or len(whitelist) == source_count:
        return []
    return whitelist


def test_all_checked_returns_empty_list():
    ui = {f"source_{i}_enabled": True for i in range(1, 4)}
    assert _reduce_whitelist(ui, 3) == []


def test_all_unchecked_returns_empty_list():
    ui = {f"source_{i}_enabled": False for i in range(1, 4)}
    assert _reduce_whitelist(ui, 3) == []


def test_partial_selection_returns_only_checked_indices():
    ui = {"source_1_enabled": True, "source_2_enabled": False, "source_3_enabled": True}
    assert _reduce_whitelist(ui, 3) == [1, 3]


def test_single_source_selected():
    ui = {"source_1_enabled": False, "source_2_enabled": True, "source_3_enabled": False}
    assert _reduce_whitelist(ui, 3) == [2]


def test_missing_keys_default_to_true():
    # If a key is absent from user_input, default=True (all checked)
    assert _reduce_whitelist({}, 3) == []  # all True → empty (show all)
