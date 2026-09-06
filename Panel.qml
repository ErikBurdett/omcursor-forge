pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC
import Quickshell
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.erikburdett.cursorforge"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  property var service: null

  readonly property string currentStyle: service ? service.style : "classic"
  readonly property string colorMode: service ? service.colorMode : "theme"
  readonly property string customColor: service ? service.customColor : "#7aa2f7"
  readonly property string effectiveColor: service ? service.effectiveColor : "#7aa2f7"
  readonly property int cursorSize: service ? service.cursorSize : 24
  readonly property bool busy: service ? service.busy : false
  readonly property bool cursorActive: service ? service.active : false
  readonly property string lastError: service ? service.lastError : ""
  readonly property string previewDir: service ? service.previewDir : ""

  readonly property var swatches: [
    "#e8e4d8", "#e0b040", "#c05a4a", "#7aa2f7",
    "#63a06a", "#9a6fc4", "#d98a4f", "#8a8f98"
  ]

  // Bumped whenever the generator rewrites the preview PNGs; every preview
  // image bounces its source on the tick because the URLs never change.
  property int previewTick: 0

  function refreshPreviews() {
    heroPreview.source = ""
    if (root.previewDir !== "")
      heroPreview.source = "file://" + root.previewDir + "/current.png"
  }

  onPreviewDirChanged: {
    refreshPreviews()
    previewTick++
  }
  Component.onCompleted: refreshPreviews()

  Connections {
    target: root.service
    ignoreUnknownSignals: true
    function onApplied() {
      root.refreshPreviews()
      root.previewTick++
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(780))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }

      Column {
        id: content
        width: panelFlick.width
        spacing: Style.space(10)

        Row {
          width: parent.width
          spacing: Style.space(10)

          BorderSurface {
            width: Style.space(52)
            height: Style.space(52)
            radius: Style.cornerRadius
            color: Style.normalFillFor(root.barForeground, Color.accent)
            borderSpec: Border.controlSpec("normal", root.barForeground, Color.accent)

            Image {
              id: heroPreview
              anchors.fill: parent
              anchors.margins: Style.space(6)
              fillMode: Image.PreserveAspectFit
              smooth: false
              cache: false
              visible: status === Image.Ready
            }
          }

          Column {
            width: parent.width - Style.space(62)
            spacing: Style.space(3)
            anchors.verticalCenter: parent.verticalCenter

            Text {
              text: "OmCursor Forge"
              color: root.barForeground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.subtitle
              font.bold: true
            }

            Text {
              width: parent.width
              text: {
                if (!root.service) return "Service unavailable"
                var label = root.service.styleLabel(root.currentStyle)
                  + " · " + root.effectiveColor
                if (root.busy) return label + " · forging…"
                return label + (root.cursorActive ? "" : " · not applied yet")
              }
              color: Color.muted
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              visible: root.lastError !== ""
              text: root.lastError
              color: Color.urgent
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
            }
          }
        }

        PanelSectionHeader { text: "Style" }

        Flow {
          width: parent.width
          spacing: Style.space(8)

          Repeater {
            model: [
              { key: "classic", label: "Classic" },
              { key: "lich", label: "Lich" },
              { key: "sword", label: "Sword" },
              { key: "wand", label: "Wand" },
              { key: "d20", label: "D20" },
              { key: "terminal", label: "Terminal" },
              { key: "image", label: "Image" }
            ]

            delegate: Column {
              id: styleTile
              required property var modelData
              readonly property bool selected: root.currentStyle === modelData.key
              spacing: Style.space(3)

              BorderSurface {
                width: Style.space(44)
                height: Style.space(44)
                radius: Style.cornerRadius
                color: styleTile.selected
                  ? Style.selectionFillFor(root.barForeground, Color.accent)
                  : Style.normalFillFor(root.barForeground, Color.accent)
                borderSpec: Border.controlSpec(styleTile.selected ? "focus" : "normal",
                  root.barForeground, Color.accent)

                Image {
                  id: tileImage
                  anchors.fill: parent
                  anchors.margins: Style.space(5)
                  fillMode: Image.PreserveAspectFit
                  smooth: false
                  cache: false
                  visible: status === Image.Ready

                  function refresh() {
                    source = ""
                    var key = styleTile.modelData.key
                    if (key === "image") {
                      var path = root.service ? String(root.service.imagePath) : ""
                      if (path !== "") source = "file://" + path
                    } else if (root.previewDir !== "") {
                      source = "file://" + root.previewDir + "/" + key + ".png"
                    }
                  }

                  Component.onCompleted: refresh()

                  Connections {
                    target: root
                    function onPreviewTickChanged() { tileImage.refresh() }
                  }
                }

                Text {
                  anchors.centerIn: parent
                  visible: tileImage.status !== Image.Ready
                  text: styleTile.modelData.key === "image" ? "…" : "↖"
                  color: root.barForeground
                  font.family: root.bar ? root.bar.fontFamily : Style.font.family
                  font.pixelSize: Style.font.heading
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: if (root.service) root.service.setStyle(styleTile.modelData.key)
                }
              }

              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: styleTile.modelData.label
                color: styleTile.selected ? root.barForeground : Color.muted
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
              }
            }
          }
        }

        Column {
          width: parent.width
          visible: root.currentStyle === "image"
          spacing: Style.space(4)

          TextField {
            id: imageField
            width: parent.width
            placeholderText: "/absolute/path/to/cursor.png"
            text: root.service ? root.service.imagePath : ""
            foreground: root.barForeground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            onAccepted: if (root.service) root.service.setImagePath(text)
          }

          Row {
            spacing: Style.space(4)

            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "Tint with cursor color"
              color: root.barForeground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.bodySmall
            }

            ToggleSwitch {
              anchors.verticalCenter: parent.verticalCenter
              checked: root.service ? root.service.imageTint === true : false
              onToggled: if (root.service) root.service.setImageTint(!root.service.imageTint)
            }
          }

          Text {
            width: parent.width
            text: "Any image ImageMagick can read; the hotspot is its top-left corner."
            color: Color.muted
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }
        }

        PanelSectionHeader { text: "Color" }

        Row {
          spacing: Style.space(6)

          Button {
            text: "Match theme"
            selected: root.colorMode === "theme"
            bordered: true
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            onClicked: if (root.service) root.service.setColorMode("theme")
          }

          Button {
            text: "Custom"
            selected: root.colorMode === "custom"
            bordered: true
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            onClicked: if (root.service) root.service.setColorMode("custom")
          }
        }

        Column {
          width: parent.width
          visible: root.colorMode === "custom"
          spacing: Style.space(6)

          Row {
            spacing: Style.space(5)

            Repeater {
              model: root.swatches

              delegate: Rectangle {
                id: swatch
                required property string modelData
                width: Style.space(18)
                height: Style.space(18)
                radius: Style.cornerRadius
                color: modelData
                border.width: root.customColor.toLowerCase() === modelData ? 2 : 1
                border.color: root.customColor.toLowerCase() === modelData
                  ? Color.accent : Color.muted

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: if (root.service) root.service.setCustomColor(swatch.modelData)
                }
              }
            }
          }

          TextField {
            id: colorField
            width: Style.space(110)
            placeholderText: "#rrggbb"
            text: root.customColor
            foreground: root.barForeground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            onAccepted: if (root.service) root.service.setCustomColor(text)
          }
        }

        PanelSectionHeader { text: "Size" }

        Row {
          spacing: Style.space(6)

          Repeater {
            model: [24, 48, 72, 96]

            delegate: Button {
              required property int modelData
              text: String(modelData)
              selected: root.cursorSize === modelData
              bordered: true
              foreground: root.barForeground
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              onClicked: if (root.service) root.service.setCursorSize(modelData)
            }
          }
        }

        PanelSectionHeader { text: "Animation" }

        Flow {
          width: parent.width
          spacing: Style.space(8)

          Repeater {
            model: [
              { label: "Animated", key: "animated" },
              { label: "Motion", key: "motion" },
              { label: "Click ripple", key: "clickRipple" },
              { label: "Left-handed", key: "leftHanded" }
            ]

            delegate: Row {
              id: optionToggle
              required property var modelData
              spacing: Style.space(3)

              Text {
                anchors.verticalCenter: parent.verticalCenter
                text: optionToggle.modelData.label
                color: root.barForeground
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.bodySmall
              }

              ToggleSwitch {
                anchors.verticalCenter: parent.verticalCenter
                checked: root.service
                  ? root.service[optionToggle.modelData.key] === true : false
                onToggled: {
                  if (!root.service) return
                  var key = optionToggle.modelData.key
                  var value = !root.service[key]
                  if (key === "animated") root.service.setAnimated(value)
                  else if (key === "motion") root.service.setMotion(value)
                  else if (key === "clickRipple") root.service.setClickRipple(value)
                  else root.service.setLeftHanded(value)
                }
              }
            }
          }
        }

        Row {
          spacing: Style.space(6)

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Speed"
            color: Color.muted
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
          }

          Repeater {
            model: ["calm", "normal", "lively"]

            delegate: Button {
              required property string modelData
              text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
              selected: root.service && root.service.speed === modelData
              bordered: true
              foreground: root.barForeground
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              onClicked: if (root.service) root.service.setSpeed(modelData)
            }
          }
        }

        Row {
          spacing: Style.space(6)
          visible: root.service ? root.service.clickRipple === true : false

          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Ripple"
            color: Color.muted
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
          }

          Repeater {
            model: ["diamond", "circle", "burst"]

            delegate: Button {
              required property string modelData
              text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
              selected: root.service && root.service.rippleShape === modelData
              bordered: true
              foreground: root.barForeground
              fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
              onClicked: if (root.service) root.service.setRippleShape(modelData)
            }
          }
        }

        Row {
          spacing: Style.space(6)
          visible: root.service ? root.service.clickRipple === true
            && root.service.bindInstalled !== true : false

          Text {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, Style.space(200))
            text: "The ripple needs a one-time mouse bind"
            color: Color.muted
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }

          Button {
            text: "Install bind"
            bordered: true
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            onClicked: if (root.service) root.service.installRippleBind()
          }
        }

        Row {
          spacing: Style.space(6)
          visible: root.service ? root.service.fractionalIssue === true : false

          Text {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, Style.space(200))
            text: "Fractional display scaling can crop cursors"
            color: Color.urgent
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }

          Button {
            text: "Fix scaling"
            bordered: true
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            onClicked: if (root.service) root.service.fixFractionalScale()
          }
        }

        PanelSectionHeader { text: "Every shape" }

        Image {
          id: galleryImage
          width: Math.min(implicitWidth, parent.width)
          fillMode: Image.PreserveAspectFit
          smooth: false
          cache: false
          visible: status === Image.Ready

          function refresh() {
            source = ""
            if (root.previewDir !== "")
              source = "file://" + root.previewDir + "/shapes.png"
          }

          Component.onCompleted: refresh()

          Connections {
            target: root
            function onPreviewTickChanged() { galleryImage.refresh() }
          }
        }

        PanelSeparator {}

        Row {
          width: parent.width
          spacing: Style.space(8)

          Button {
            text: "Restore system cursor"
            bordered: true
            enabled: root.cursorActive && !root.busy
            opacity: enabled ? 1 : 0.4
            foreground: root.barForeground
            fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
            onClicked: if (root.service) root.service.runReset()
          }
        }

        Text {
          width: parent.width
          text: "Applies live. Also editable at ~/.config/cursorforge/settings.json"
          color: Color.muted
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.Wrap
        }
      }
      }
    }
  }
}
