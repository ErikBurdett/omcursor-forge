## What does this change?

## Checklist

- [ ] `pytest -q tests/` passes
- [ ] `omarchy plugin validate .` passes
- [ ] QML parses (`/usr/lib/qt6/bin/qmlformat -n *.qml`) — if QML changed
- [ ] Art changes reviewed at native size, enlarged, and on light + dark
      backgrounds (`cursorgen.py preview`) — if art changed
- [ ] `CHANGELOG.md` updated
- [ ] No new symlinks, network access, privileged commands, or non-stdlib
      Python imports
