import core.version as version
from core.loreforge_meta import (
    LOREFORGE_META_KEY,
    ensure_entry_uuid,
    get_entry_uuid,
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
    assert get_entry_uuid(stamped) is not None
    assert is_native_entry(stamped) is True


def test_stamp_entry_preserves_existing_entry_uuid():
    entry = {
        "messages": [],
        "tags": [],
        LOREFORGE_META_KEY: {
            "version": "0.3.7",
            "native": True,
            "validated_at": "2026-05-11T12:00:00Z",
            "entry_uuid": "existing-entry-uuid",
        },
    }

    stamped = stamp_entry(entry)

    assert get_entry_uuid(stamped) == "existing-entry-uuid"
    assert get_entry_uuid(entry) == "existing-entry-uuid"
    assert stamped[LOREFORGE_META_KEY]["version"] == version.LOREFORGE_VERSION


def test_ensure_entry_uuid_adds_uuid_without_mutating_original():
    entry = {"messages": [], "tags": []}

    entry_with_uuid = ensure_entry_uuid(entry)

    assert get_entry_uuid(entry) is None
    assert get_entry_uuid(entry_with_uuid) is not None
    assert entry_with_uuid[LOREFORGE_META_KEY] == {
        "entry_uuid": get_entry_uuid(entry_with_uuid),
    }
    assert is_native_entry(entry_with_uuid) is False
    assert entry_with_uuid is not entry


def test_ensure_entry_uuid_preserves_existing_uuid():
    entry = {LOREFORGE_META_KEY: {"entry_uuid": "existing-entry-uuid"}}

    entry_with_uuid = ensure_entry_uuid(entry)

    assert get_entry_uuid(entry_with_uuid) == "existing-entry-uuid"


def test_ensure_entry_uuid_preserves_partial_loreforge_metadata():
    entry = {
        LOREFORGE_META_KEY: {
            "version": "0.5.9",
            "custom_note": "keep me",
        }
    }

    entry_with_uuid = ensure_entry_uuid(entry)

    assert get_entry_uuid(entry_with_uuid) is not None
    assert entry_with_uuid[LOREFORGE_META_KEY]["version"] == "0.5.9"
    assert entry_with_uuid[LOREFORGE_META_KEY]["custom_note"] == "keep me"
    assert "native" not in entry_with_uuid[LOREFORGE_META_KEY]
    assert "validated_at" not in entry_with_uuid[LOREFORGE_META_KEY]


def test_native_entry_detection_does_not_require_entry_uuid():
    old_native = {LOREFORGE_META_KEY: {"version": "0.3.7", "native": True}}

    assert get_entry_uuid(old_native) is None
    assert is_native_entry(old_native) is True


def test_stamp_entries_marks_each_dict_entry():
    entries = [{"messages": [], "tags": []}]

    stamped_entries = stamp_entries(entries)

    assert stamped_entries is not entries
    assert stamped_entries[0] is not entries[0]
    assert get_entry_uuid(stamped_entries[0]) is not None
    assert is_native_dataset(stamped_entries) is True
