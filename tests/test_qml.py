"""Run the real service/widget in Qt with inert shell and filesystem adapters.

No Quickshell process is launched and no cursor/settings files are touched.
The picker is a small injection target; its visual controls are out of scope.
"""

import os
import json
from pathlib import Path
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_service_lifecycle_in_qml(tmp_path):
    runner = shutil.which("qmltestrunner")
    if not runner:
        runner = next((str(path) for path in (
            Path("/usr/lib/qt6/bin/qmltestrunner"),
            Path("/usr/lib/qt6/libexec/qmltestrunner"),
        ) if path.is_file()), None)
    if not runner:
        if os.environ.get("CI"):
            pytest.fail("Qt 6 qmltestrunner is required in CI")
        pytest.skip("Qt 6 qmltestrunner is not installed")

    plugin = tmp_path / "plugin"
    plugin.mkdir()
    for name in ("BarWidget.qml", "Service.qml"):
        shutil.copy2(REPO / name, plugin / name)
    shutil.copytree(REPO / "bridge", plugin / "bridge")
    shutil.copy2(REPO / "tests/qml/tst_service_lifecycle.qml", tmp_path)
    previews = tmp_path / "icons/OmCursorForge/previews"
    previews.mkdir(parents=True)
    shutil.copy2(REPO / "preview.png", previews / "current.png")
    (plugin / "Panel.qml").write_text("""
import QtQuick
Item {
  objectName: "picker"
  property var bar
  property var settings
  property var anchorItem
  property var hostWidget
  property var service
  property bool opened: false
  function open() { opened = true }
  function close() { opened = false }
  function toggle() { opened = !opened }
  function closeForPopoutSwitch() { close() }
}
""")

    # Only the host APIs these entry points consume. Processes and FileView
    # are inert, so Service.qml's real lifecycle runs without desktop effects.
    modules = {
        "Quickshell": {
            "Quickshell": """pragma Singleton
import QtQml
QtObject { function env(name) { return TEST_HOME } }
""".replace("TEST_HOME", json.dumps(str(tmp_path))),
        },
        "Quickshell/Io": {
            "Process": """import QtQml
QtObject {
  property bool running: false
  property var stdout
  property var stderr
  signal exited(int exitCode)
  function exec(command) {}
}
""",
            "StdioCollector": 'import QtQml\nQtObject { property string text: "" }',
            "IpcHandler": 'import QtQml\nQtObject { property string target: "" }',
            "FileView": """import QtQml
QtObject {
  property string path
  property bool watchChanges
  property bool printErrors
  signal loaded()
  signal fileChanged()
  signal loadFailed()
  function text() { return "" }
  function reload() {}
}
""",
        },
        "qs/Commons": {
            "Color": """pragma Singleton
import QtQuick
QtObject {
  property color accent: "#7aa2f7"
  property color foreground: "#ffffff"
}
""",
            "Style": """pragma Singleton
import QtQml
QtObject {
  property var font: ({family: "sans-serif", body: 12, bodySmall: 10})
  function space(value) { return value }
}
""",
        },
        "qs/Ui": {
            "BarWidget": """import QtQuick
Item {
  property var bar
  property string moduleName
  property var settings: ({})
  readonly property bool vertical: bar ? bar.vertical : false
  property int barSize: 24
  function setting(name, fallback) {
    return settings[name] === undefined ? fallback : settings[name]
  }
}
""",
        },
    }
    imports = tmp_path / "imports"
    for module, types in modules.items():
        directory = imports / module
        directory.mkdir(parents=True)
        entries = [f"module {module.replace('/', '.')}\n"]
        for name, source in types.items():
            (directory / f"{name}.qml").write_text(source)
            prefix = "singleton " if source.startswith("pragma Singleton") else ""
            entries.append(f"{prefix}{name} 1.0 {name}.qml\n")
        (directory / "qmldir").write_text("".join(entries))

    result = subprocess.run(
        [runner, "-input", str(tmp_path), "-import", str(imports)],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"},
        text=True, capture_output=True, timeout=30,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "QWARN" not in output and "QFATAL" not in output, output
