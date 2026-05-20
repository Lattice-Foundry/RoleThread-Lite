import inspect

import pytest

from core import runtime
import core.version as version
import ui.ui_settings as ui_settings


def test_runtime_constants_pin_python_3145():
    assert version.OFFICIAL_PYTHON_VERSION == "3.14.5"
    assert version.MIN_SUPPORTED_PYTHON == (3, 14, 4)
    assert version.MAX_TESTED_PYTHON == (3, 14, 5)


def test_minimum_python_3144_is_supported():
    status = runtime.get_python_runtime_status((3, 14, 4))

    assert status.current_version == "3.14.4"
    assert status.is_officially_supported is False
    assert status.is_below_minimum is False
    assert status.is_newer_than_tested is False
    assert status.status_label == runtime.RUNTIME_STATUS_SUPPORTED
    assert "supported Python runtime" in status.message


def test_python_below_3144_is_unsupported():
    status = runtime.get_python_runtime_status((3, 14, 3))

    assert status.current_version == "3.14.3"
    assert status.is_officially_supported is False
    assert status.is_below_minimum is True
    assert status.is_allowed is False
    assert status.status_label == runtime.RUNTIME_STATUS_UNSUPPORTED_OLDER
    assert "Please install Python 3.14.5" in status.message


def test_exact_python_3145_is_officially_supported():
    status = runtime.get_python_runtime_status((3, 14, 5))

    assert status.current_version == "3.14.5"
    assert status.is_officially_supported is True
    assert status.is_below_minimum is False
    assert status.is_newer_than_tested is False
    assert status.is_allowed is True
    assert status.status_label == runtime.RUNTIME_STATUS_SUPPORTED
    assert "official supported Python runtime" in status.message


def test_python_above_3145_is_allowed_but_untested():
    status = runtime.get_python_runtime_status((3, 14, 6))

    assert status.current_version == "3.14.6"
    assert status.is_officially_supported is False
    assert status.is_below_minimum is False
    assert status.is_newer_than_tested is True
    assert status.is_allowed is True
    assert status.status_label == runtime.RUNTIME_STATUS_UNTESTED_NEWER
    assert "not officially supported yet" in status.message


def test_validate_python_runtime_raises_clear_error_for_old_runtime():
    with pytest.raises(RuntimeError, match="Please install Python 3.14.5"):
        runtime.validate_python_runtime((3, 13, 9))


def test_validate_python_runtime_allows_exact_and_newer_versions():
    assert runtime.validate_python_runtime((3, 14, 4)).is_allowed is True
    assert runtime.validate_python_runtime((3, 14, 5)).is_allowed is True
    assert runtime.validate_python_runtime((3, 15, 0)).is_allowed is True


def test_runtime_module_has_no_streamlit_dependency():
    source = inspect.getsource(runtime)

    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert "st.session_state" not in source


def test_settings_about_consumes_runtime_status_without_version_logic():
    source = inspect.getsource(ui_settings)

    assert "get_python_runtime_status" in source
    assert "MIN_SUPPORTED_PYTHON" not in source
    assert "MAX_TESTED_PYTHON" not in source
