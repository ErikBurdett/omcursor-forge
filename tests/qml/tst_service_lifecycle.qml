import QtQuick
import QtTest
import "plugin/bridge" as Bridge

TestCase {
  id: testCase
  name: "CursorForgeServiceLifecycle"

  Component {
    id: hostComponent
    QtObject {
      property var ownService: null
      property bool vertical: false
      property color barForeground: "#ffffff"
      property string fontFamily: "sans-serif"
      property var shell: QtObject {
        function serviceFor(id) {
          testCase.compare(id, "io.github.erikburdett.cursorforge")
          return ownService
        }
      }
    }
  }

  function create(name, properties) {
    var component = Qt.createComponent("plugin/" + name + ".qml")
    compare(component.status, Component.Ready, component.errorString())
    var item = createTemporaryObject(component, testCase, properties || {})
    verify(item !== null, component.errorString())
    return item
  }

  function service() {
    return create("Service")
  }

  function widget(ownService) {
    var host = createTemporaryObject(hostComponent, testCase, {
      ownService: ownService || null
    })
    return create("BarWidget", {bar: host})
  }

  function picker(widget) {
    var item = findChild(widget, "picker")
    verify(item !== null)
    return item
  }

  function init() { compare(Bridge.ServiceBridge.service, null) }

  function test_unavailable_is_harmless() {
    var view = widget()
    compare(view.cursorService, null)
    compare(picker(view).service, null)
    compare(view.tooltipLabel(), "OmCursor Forge")
  }

  function test_custom_bar_service_first() {
    var owner = service()
    var view = widget()
    compare(view.cursorService, owner)
    compare(picker(view).service, owner)
    view.open()
    compare(view.opened, true)
    view.close()
    compare(view.opened, false)
  }

  function test_custom_bar_widget_first() {
    var first = widget()
    var second = widget()
    var owner = service()
    compare(first.cursorService, owner)
    compare(second.cursorService, owner)
    compare(picker(first).service, owner)
    compare(picker(second).service, owner)
    owner.style = "sword"
    verify(first.tooltipLabel().indexOf("Sword") !== -1)
  }

  function test_default_bar_prefers_host_service() {
    var hosted = service()
    var view = widget(hosted)
    var replacement = service()
    compare(Bridge.ServiceBridge.service, replacement)
    compare(view.cursorService, hosted)
    compare(picker(view).service, hosted)
    view.bar.ownService = null
    compare(view.cursorService, replacement)
  }

  function test_disable_and_reenable() {
    var view = widget()
    var owner = service()
    owner.destroy()
    tryCompare(Bridge.ServiceBridge, "service", null)
    compare(view.cursorService, null)
    compare(picker(view).service, null)
    var replacement = service()
    compare(view.cursorService, replacement)
    compare(picker(view).service, replacement)
  }

  function test_retiring_service_preserves_replacement() {
    var oldOwner = service()
    var view = widget()
    var replacement = service()
    oldOwner.destroy()
    wait(0)
    compare(Bridge.ServiceBridge.service, replacement)
    compare(view.cursorService, replacement)
    compare(picker(view).service, replacement)
  }
}
