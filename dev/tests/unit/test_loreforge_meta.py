import core.version as version
from core.loreforge_meta import (
    LOREFORGE_META_KEY,
    get_loreforge_meta,
    is_native_dataset,
    is_native_entry,
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
