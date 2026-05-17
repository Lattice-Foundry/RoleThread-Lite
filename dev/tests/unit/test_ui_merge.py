import json

from core.rolethread_meta import ROLETHREAD_META_KEY
from ui.ui_merge import _merged_download_payload


def test_merged_download_payload_uses_saved_entries_with_rolethread_metadata():
    saved_entries = [
        {
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            "tags": ["merged"],
            ROLETHREAD_META_KEY: {
                "version": "0.7.10",
                "native": True,
                "entry_uuid": "entry-uuid",
                "dataset_uuid": "dataset-uuid",
            },
        }
    ]

    payload = _merged_download_payload(saved_entries)

    assert json.loads(payload.decode("utf-8")) == saved_entries[0]

