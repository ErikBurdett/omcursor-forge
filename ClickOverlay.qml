import QtQuick
import Quickshell
import Quickshell.Wayland

// Click-ripple overlay: a brief pixel-art ring burst at the pointer on every
// left click, driven by the service's ripple(x, y) signal (which the
// optional non-consuming mouse bind feeds). The window is a visual-only
// layer surface: empty input mask, no keyboard focus, no exclusion — it can
// never block or steal a click.
Item {
  id: root

  property var shell: null
  property var manifest: null
  readonly property string pluginId: "io.github.erikburdett.cursorforge"
  readonly property var service: shell ? shell.serviceFor(pluginId) : null
  readonly property string previewDir: service ? service.previewDir : ""

  readonly property int frameCount: 4
  readonly property int rippleSize: 96  // 48px art shown at 2x, nearest

  property real rippleX: 0
  property real rippleY: 0
  property int frame: 0
  property bool playing: false
  property var targetScreen: Quickshell.screens.length > 0
    ? Quickshell.screens[0] : null

  function screenFor(x, y) {
    var screens = Quickshell.screens
    for (var at = 0; at < screens.length; at++) {
      var candidate = screens[at]
      if (x >= candidate.x && x < candidate.x + candidate.width
          && y >= candidate.y && y < candidate.y + candidate.height)
        return candidate
    }
    return screens.length > 0 ? screens[0] : null
  }

  function play(x, y) {
    var where = screenFor(x, y)
    if (!where || previewDir === "") return
    targetScreen = where
    rippleX = x - where.x
    rippleY = y - where.y
    frame = 0
    playing = true
    frameTimer.restart()
  }

  Connections {
    target: root.service
    ignoreUnknownSignals: true
    function onRipple(x, y) { root.play(x, y) }
  }

  Timer {
    id: frameTimer
    interval: 65
    repeat: true
    running: root.playing
    onTriggered: {
      if (root.frame >= root.frameCount - 1) {
        root.playing = false
        return
      }
      root.frame++
    }
  }

  PanelWindow {
    visible: root.playing
    screen: root.targetScreen
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "cursorforge-ripple"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore
    mask: Region {}

    Image {
      x: root.rippleX - width / 2
      y: root.rippleY - height / 2
      width: root.rippleSize
      height: root.rippleSize
      smooth: false
      cache: false
      source: root.playing && root.previewDir !== ""
        ? "file://" + root.previewDir + "/ripple_" + root.frame + ".png" : ""
      visible: status === Image.Ready
    }
  }
}
