import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.erikburdett.cursorforge"

  readonly property var cursorService: bar && bar.shell
    ? bar.shell.serviceFor(moduleName) : null
  readonly property bool showStyleName: setting("showStyleName", false) === true
  readonly property bool opened: panelLoader.item
    ? panelLoader.item.opened === true : false
  readonly property string previewFile: cursorService
    ? cursorService.previewDir + "/current.png" : ""

  implicitWidth: vertical ? barSize : content.implicitWidth + Style.space(8)
  implicitHeight: vertical ? content.implicitHeight + Style.space(8) : barSize

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function toggle() { if (panelLoader.item) panelLoader.item.toggle() }
  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function injectPanel() {
    if (!panelLoader.item) return
    panelLoader.item.bar = root.bar
    panelLoader.item.settings = root.settings
    panelLoader.item.anchorItem = root
    panelLoader.item.hostWidget = root
    panelLoader.item.service = root.cursorService
  }

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()
  onCursorServiceChanged: injectPanel()

  // The generator rewrites current.png in place under the same URL, so the
  // image element must be bounced to pick up a new render.
  function refreshPreview() {
    preview.source = ""
    if (root.previewFile !== "")
      preview.source = "file://" + root.previewFile
  }

  function tooltipLabel() {
    if (!cursorService) return "Cursor Forge"
    return "Cursor Forge — " + cursorService.styleLabel(cursorService.style)
      + " · " + cursorService.effectiveColor
      + (cursorService.active ? "" : " (not applied)")
  }

  Connections {
    target: root.cursorService
    ignoreUnknownSignals: true
    function onApplied() { root.refreshPreview() }
  }

  Component.onCompleted: refreshPreview()
  onPreviewFileChanged: refreshPreview()

  Loader {
    id: panelLoader
    active: true
    visible: false
    source: Qt.resolvedUrl("Panel.qml")
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  Row {
    id: content
    anchors.centerIn: parent
    spacing: Style.space(4)

    Item {
      width: Style.space(16)
      height: Style.space(16)
      anchors.verticalCenter: parent.verticalCenter

      Image {
        id: preview
        anchors.fill: parent
        fillMode: Image.PreserveAspectFit
        smooth: false
        cache: false
        asynchronous: true
        visible: status === Image.Ready
      }

      Text {
        anchors.centerIn: parent
        visible: preview.status !== Image.Ready
        text: "↖"
        color: root.bar ? root.bar.barForeground : Color.foreground
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.body
      }
    }

    Text {
      visible: root.showStyleName && !root.vertical
      anchors.verticalCenter: parent.verticalCenter
      text: root.cursorService
        ? root.cursorService.styleLabel(root.cursorService.style) : ""
      color: root.bar ? root.bar.barForeground : Color.foreground
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.bodySmall
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.toggle()
    onWheel: function(wheel) {
      if (root.cursorService) root.cursorService.cycleStyle()
    }
    onEntered: if (root.bar) root.bar.showTooltip(root, root.tooltipLabel())
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
