# This software is licensed under the "GPLv3" License as described in the "LICENSE" file,
# which should be included with this package. The terms are also available at
# http://www.gnu.org/licenses/gpl-3.0.html

"""Headless GUI smoke tests.

These construct the real application and its dialogs under PyQt6 so that CI
(running them headless via xvfb) catches runtime errors -- most importantly the
unscoped-enum errors that don't surface in the ``core``/``hscommon`` tests. Run
locally with ``QT_QPA_PLATFORM=offscreen pytest qt/tests``.
"""

import importlib
import pkgutil

import pytest

import qt
from qt.app import DupeGuru
from qt.prioritize_dialog import PrioritizeDialog


@pytest.fixture
def dgapp(qtbot):
    app = DupeGuru()
    yield app


def test_all_qt_modules_import(qtbot):
    # Importing every module catches moved symbols (e.g. QAction) and any enum
    # usage evaluated at import time, across the whole qt package.
    failures = []
    for info in pkgutil.walk_packages(qt.__path__, prefix="qt."):
        if ".tests" in info.name:
            continue
        try:
            importlib.import_module(info.name)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{info.name}: {exc}")
    assert not failures, "modules failed to import:\n" + "\n".join(failures)


def test_app_and_main_window_construct(dgapp):
    # Constructing DupeGuru builds the main window plus the directories, problem,
    # ignore-list and exclude-list dialogs and the about box.
    assert dgapp.main_window is not None


def test_on_demand_dialogs_construct(dgapp):
    parent = dgapp.main_window
    preferences = dgapp._get_preferences_dialog_class()(parent, dgapp)
    assert preferences is not None
    prioritize = PrioritizeDialog(parent, dgapp)
    assert prioritize is not None
