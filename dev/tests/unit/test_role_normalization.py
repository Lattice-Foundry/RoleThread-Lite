from core.role_normalization import (
    is_known_role_variant,
    normalize_entry_roles,
    normalize_role,
)


def test_normalize_role_maps_known_typos_and_variants():
    assert normalize_role(" USER ") == ("user", True)
    assert normalize_role("uesr") == ("user", True)
    assert normalize_role("ASSITANT") == ("assistant", True)
    assert normalize_role("Bot") == ("assistant", True)
    assert normalize_role("sytem") == ("system", True)


def test_normalize_role_preserves_potential_character_names():
    assert normalize_role("Scott") == ("Scott", False)
    assert normalize_role(" Emma ") == (" Emma ", False)
    assert is_known_role_variant("Scott") is False


def test_is_known_role_variant_detects_dictionary_hits():
    assert is_known_role_variant("instruction") is True
    assert is_known_role_variant("completion") is True
    assert is_known_role_variant("context") is True


def test_normalize_entry_roles_deep_copies_and_preserves_unknown_roles():
    entry = {
        "messages": [
            {"role": "sys", "content": "System"},
            {"role": "usr", "content": "Hi"},
            {"role": "ASSITANT", "content": "Hello"},
            {"role": "Scott", "content": "Custom"},
        ],
        "tags": [],
    }

    normalized, changed = normalize_entry_roles(entry)

    assert changed is True
    assert normalized["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "Scott", "content": "Custom"},
    ]
    assert entry["messages"][0]["role"] == "sys"
