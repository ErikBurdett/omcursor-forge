"""Contract tests for manifest.json against the Omarchy plugin schema.

Mirrors the checks in Omarchy's PluginRegistry.validateManifest and
omarchy-plugin-validate so a refactor that would break installation fails in
CI instead of as a console warning at a user's login.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KIND_ENTRY_POINTS = {
    "bar": "bar",
    "bar-widget": "barWidget",
    "menu": "menu",
    "overlay": "overlay",
    "panel": "panel",
    "service": "service",
}


def manifest():
    with open(REPO / "manifest.json", encoding="utf-8") as handle:
        return json.load(handle)


def test_manifest_is_at_repo_root():
    assert (REPO / "manifest.json").is_file()


def test_schema_version_is_the_number_one():
    value = manifest()["schemaVersion"]
    assert value == 1 and isinstance(value, int)


def test_required_fields_present():
    data = manifest()
    for field in ("id", "name", "version", "kinds", "entryPoints"):
        assert field in data, f"missing required field {field}"


def test_id_shape():
    plugin_id = manifest()["id"]
    assert re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", plugin_id)
    assert ".." not in plugin_id and "/" not in plugin_id
    assert not plugin_id.startswith("omarchy.")
    assert plugin_id == "io.github.erikburdett.cursorforge"


def test_kinds_have_entry_points_and_files_exist():
    data = manifest()
    assert isinstance(data["kinds"], list) and data["kinds"]
    assert isinstance(data["entryPoints"], dict)
    for kind in data["kinds"]:
        key = KIND_ENTRY_POINTS[kind]
        assert key in data["entryPoints"], f"kind {kind} needs entryPoints.{key}"
    for key, value in data["entryPoints"].items():
        assert not value.startswith("/") and ".." not in value and "\n" not in value
        assert (REPO / value).is_file(), f"entry point {value} does not exist"


def test_bar_widget_defaults_match_schema():
    widget = manifest()["barWidget"]
    assert widget["defaultSection"] in ("left", "center", "right")
    defaults = widget["defaults"]
    schema_keys = {entry["key"]: entry for entry in widget["schema"]}
    assert set(defaults) == set(schema_keys)
    for key, entry in schema_keys.items():
        assert entry["defaultValue"] == defaults[key]


def test_no_symlinks_packaged():
    for path in REPO.rglob("*"):
        if ".git" in path.parts:
            continue
        assert not path.is_symlink(), f"symlink packaged: {path}"


def test_version_is_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", manifest()["version"])
