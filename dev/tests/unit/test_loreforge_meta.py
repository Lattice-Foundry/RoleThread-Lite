import core.version as version
from core.loreforge_meta import (
    LOREFORGE_META_KEY,
    get_loreforge_meta,
    is_native_dataset,
    is_native_entry,
    stamp_entry,
    stamp_entries,
)


def test_version_constant_exists():
    major, minor, patch = version.LOREFORGE_VERSION.split(".")

    assert len((major, minor, patch)) == 3
    assert all(part.isdigit() for part in (major, minor, patch))


def test_native_entry_detection_requires_loreforge_signature():
    native = {LOREFORGE_META_KEY: {"version": "0.1.0", "native": True}}
    foreign = {"messages": [], "tags": []}
    malformed = {LOREFORGE_META_KEY: "not metadata"}

    assert get_loreforge_meta(native) == {"version": "0.1.0", "native": True}
    assert get_loreforge_meta(malformed) is None
    assert is_native_entry(native) is True
    assert is_native_entry(foreign) is False
    assert is_native_entry(malformed) is False


def test_native_dataset_requires_all_entries_to_be_native():
    native = {LOREFORGE_META_KEY: {"native": True}}
    foreign = {"messages": [], "tags": []}

    assert is_native_dataset([native, native]) is True
    assert is_native_dataset([native, foreign]) is False
    assert is_native_dataset([foreign]) is False
    assert is_native_dataset([]) is False


def test_stamp_entry_marks_copy_as_native_loreforge_data():
    entry = {"messages": [], "tags": []}

    stamped = stamp_entry(entry)

    assert entry == {"messages": [], "tags": []}
    assert stamped[LOREFORGE_META_KEY]["version"] == version.LOREFORGE_VERSION
    assert stamped[LOREFORGE_META_KEY]["native"] is True
    assert stamped[LOREFORGE_META_KEY]["validated_at"].endswith("Z")
    assert is_native_entry(stamped) is True


def test_stamp_entries_marks_each_dict_entry():
    entries = [{"messages": [], "tags": []}]

    stamped_entries = stamp_entries(entries)

    assert stamped_entries is not entries
    assert stamped_entries[0] is not entries[0]
    assert is_native_dataset(stamped_entries) is True
