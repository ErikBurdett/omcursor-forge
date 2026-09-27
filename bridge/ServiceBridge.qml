pragma Singleton

import QtQml

// Share only Cursor Forge's service within this QML engine. Replacement bars
// intentionally have no generic service lookup. A QML property keeps widgets
// reactive when the service starts after them or is disabled and recreated.
QtObject {
  property var service: null
}
