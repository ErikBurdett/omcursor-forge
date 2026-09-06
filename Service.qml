import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons

// Cursor Forge service. Owns the cursor settings, watches the settings file
// and the Omarchy theme, and drives cursorgen.py to build + apply the theme.
Item {
  id: root

  property var shell: null
  property var manifest: null
  readonly property string pluginId: "io.github.erikburdett.cursorforge"
  readonly property var styles: ["classic", "skeleton", "lich", "sword", "wand", "image"]
  readonly property var sizes: [24, 48, 72, 96]

  // Mirrors ~/.config/cursorforge/settings.json. `active` means the user has
  // applied Cursor Forge at least once and wants it restored at login;
  // until then the generator only renders previews and never touches the
  // system cursor configuration.
  property string style: "classic"
  property string colorMode: "theme"
  property string customColor: "#7aa2f7"
  property string imagePath: ""
  property string imageHotspot: "0,0"
  property int cursorSize: 24
  property bool leftHanded: false
  property bool animated: true
  property bool motion: true
  property string speed: "normal"
  property string rippleShape: "diamond"
  property bool clickRipple: true
  property bool active: false
  readonly property var speeds: ["calm", "normal", "lively"]
  readonly property var rippleShapes: ["diamond", "circle", "burst"]

  readonly property bool busy: generator.running
  property bool pendingApply: false
  property string lastError: ""
  property int previewVersion: 0
  property bool settingsLoaded: false

  signal applied()
  signal ripple(real x, real y)

  readonly property string pluginSourceDir: {
    var source = manifest && manifest.__sourceDir ? String(manifest.__sourceDir) : ""
    if (source.length > 0 && source.length <= 4096 && source.charAt(0) === "/")
      return source.replace(/\/+$/, "")
    return Quickshell.env("HOME") + "/.config/omarchy/plugins/" + pluginId
  }
  readonly property string generatorPath: pluginSourceDir + "/cursorgen.py"
  readonly property string pythonPath: "/usr/bin/python3"
  readonly property string configHome: {
    var xdg = Quickshell.env("XDG_CONFIG_HOME")
    return xdg && xdg !== "" ? xdg : Quickshell.env("HOME") + "/.config"
  }
  readonly property string settingsPath: configHome + "/cursorforge/settings.json"
  readonly property string dataHome: {
    var xdg = Quickshell.env("XDG_DATA_HOME")
    return xdg && xdg !== "" ? xdg : Quickshell.env("HOME") + "/.local/share"
  }
  readonly property string previewDir: dataHome + "/icons/CursorForge/previews"

  // Color.accent renders as #aarrggbb; the generator wants #rrggbb.
  function colorToHex(value) {
    var text = String(value)
    return text.length === 9 ? "#" + text.slice(3) : text
  }

  function isValidColor(text) {
    return /^#[0-9a-fA-F]{6}$/.test(String(text))
  }

  readonly property string effectiveColor: colorMode === "theme"
    ? colorToHex(Color.accent) : customColor

  function styleLabel(name) {
    if (name === "skeleton") return "Skeleton hand"
    if (name === "lich") return "Lich sleeve"
    if (name === "sword") return "Sword"
    if (name === "wand") return "Wand"
    if (name === "image") return "Custom image"
    return "Classic arrow"
  }

  function setStyle(next) {
    if (styles.indexOf(next) < 0) return false
    style = next
    requestApply()
    return true
  }

  function cycleStyle() {
    var usable = imagePath !== "" ? styles
      : styles.filter(function(name) { return name !== "image" })
    var at = usable.indexOf(style)
    setStyle(usable[(at + 1) % usable.length])
  }

  function setColorMode(mode) {
    if (mode !== "theme" && mode !== "custom") return false
    colorMode = mode
    requestApply()
    return true
  }

  function setCustomColor(hex) {
    if (!isValidColor(hex)) return false
    customColor = String(hex).toLowerCase()
    colorMode = "custom"
    requestApply()
    return true
  }

  function setImagePath(path) {
    var clean = String(path || "").trim()
    if (clean === "" || clean.charAt(0) !== "/") return false
    imagePath = clean
    style = "image"
    requestApply()
    return true
  }

  function setCursorSize(size) {
    if (sizes.indexOf(Number(size)) < 0) return false
    cursorSize = Number(size)
    requestApply()
    return true
  }

  function setLeftHanded(enabled) {
    leftHanded = enabled === true
    requestApply()
    return true
  }

  function setAnimated(enabled) {
    animated = enabled === true
    requestApply()
    return true
  }

  function setClickRipple(enabled) {
    clickRipple = enabled === true
    requestApply()
    return true
  }

  function setMotion(enabled) {
    motion = enabled === true
    requestApply()
    return true
  }

  function setSpeed(next) {
    if (speeds.indexOf(next) < 0) return false
    speed = next
    requestApply()
    return true
  }

  function setRippleShape(next) {
    if (rippleShapes.indexOf(next) < 0) return false
    rippleShape = next
    requestApply()
    return true
  }

  // Fired by the (optional) non-consuming mouse bind on every left click;
  // resolves the pointer position and hands it to the ripple overlay.
  function triggerRipple() {
    if (!clickRipple) return "off"
    if (!cursorPosQuery.running) cursorPosQuery.exec(["/usr/bin/hyprctl", "cursorpos"])
    return "ok"
  }

  function setImageHotspot(spot) {
    if (!/^\d{1,2},\d{1,2}$/.test(String(spot))) return false
    imageHotspot = String(spot)
    if (style === "image") requestApply()
    return true
  }

  // A real apply: the user asked for this cursor. Debounced so a theme
  // switch or a fast series of clicks runs the generator once.
  function requestApply() {
    active = true
    // A newer apply supersedes any reset still waiting on the generator.
    pendingReset = false
    applyTimer.restart()
  }

  function runGenerator(fullApply) {
    if (generator.running) {
      pendingApply = true
      return
    }
    if (style === "image" && imagePath === "") {
      lastError = "Pick an image file first"
      return
    }
    lastError = ""
    var argv = [pythonPath, "-I", generatorPath, "apply",
      "--style", style, "--color", effectiveColor,
      "--color-mode", colorMode, "--custom-color", customColor,
      "--size", String(cursorSize)]
    if (style === "image") argv.push("--image", imagePath,
      "--image-hotspot", imageHotspot)
    if (leftHanded) argv.push("--left-handed")
    if (!animated) argv.push("--no-animation")
    if (!motion) argv.push("--no-motion")
    argv.push("--speed", speed, "--ripple-shape", rippleShape)
    if (!clickRipple) argv.push("--no-click-ripple")
    if (!fullApply) argv.push("--no-apply", "--no-save")
    generator.exec(argv)
  }

  property bool pendingReset: false

  function runReset() {
    if (generator.running) {
      // Queue behind the in-flight run so Restore never silently no-ops.
      pendingReset = true
      pendingApply = false
      return
    }
    active = false
    pendingApply = false
    applyTimer.stop()
    lastError = ""
    generator.exec([pythonPath, "-I", generatorPath, "reset"])
  }

  // Convenience presets over the animation switches:
  //   static — single-frame theme, no animation at all
  //   glints — in-place sparkles only, no sprite movement
  //   full   — sprite motion and glints
  function setMode(name) {
    if (name === "static") {
      animated = false
    } else if (name === "glints") {
      animated = true
      motion = false
    } else if (name === "full") {
      animated = true
      motion = true
    } else {
      return false
    }
    requestApply()
    return true
  }

  readonly property string mode: !animated ? "static"
    : (motion ? "full" : "glints")

  function handleResult(text) {
    var report = null
    try { report = JSON.parse(text) } catch (error) { report = null }
    if (!report || report.ok !== true) {
      lastError = report && report.error ? String(report.error)
        : "The cursor generator failed; see the shell log"
      return
    }
    if (report.warnings && report.warnings.length > 0)
      lastError = String(report.warnings[0])
    previewVersion++
    applied()
  }

  function adoptSettings(text) {
    var parsed = null
    try { parsed = JSON.parse(text) } catch (error) { parsed = null }
    var firstLoad = !settingsLoaded
    settingsLoaded = true
    if (!parsed || typeof parsed !== "object") parsed = {}

    var nextStyle = styles.indexOf(String(parsed.style)) >= 0
      ? String(parsed.style) : style
    var nextMode = parsed.colorMode === "custom" ? "custom" : "theme"
    var nextColor = isValidColor(parsed.customColor)
      ? String(parsed.customColor).toLowerCase() : customColor
    var nextImage = typeof parsed.imagePath === "string" ? parsed.imagePath : imagePath
    var nextHotspot = /^\d{1,2},\d{1,2}$/.test(String(parsed.imageHotspot))
      ? String(parsed.imageHotspot) : imageHotspot
    var nextSize = sizes.indexOf(Number(parsed.size)) >= 0
      ? Number(parsed.size) : cursorSize
    var nextLeftHanded = parsed.leftHanded === true
    var nextAnimated = parsed.animated !== false
    var nextMotion = parsed.motion !== false
    var nextSpeed = speeds.indexOf(String(parsed.speed)) >= 0
      ? String(parsed.speed) : speed
    var nextRippleShape = rippleShapes.indexOf(String(parsed.rippleShape)) >= 0
      ? String(parsed.rippleShape) : rippleShape
    var nextClickRipple = parsed.clickRipple !== false
    var nextActive = parsed.active === true
    var changed = nextStyle !== style || nextMode !== colorMode
      || nextColor !== customColor || nextImage !== imagePath
      || nextHotspot !== imageHotspot || nextSize !== cursorSize
      || nextLeftHanded !== leftHanded || nextAnimated !== animated
      || nextMotion !== motion || nextSpeed !== speed
      || nextRippleShape !== rippleShape
      || nextClickRipple !== clickRipple || nextActive !== active

    style = nextStyle
    colorMode = nextMode
    customColor = nextColor
    imagePath = nextImage
    imageHotspot = nextHotspot
    cursorSize = nextSize
    leftHanded = nextLeftHanded
    animated = nextAnimated
    motion = nextMotion
    speed = nextSpeed
    rippleShape = nextRippleShape
    clickRipple = nextClickRipple
    active = nextActive

    if (firstLoad) {
      // Reassert the cursor at shell start when the user opted in, or just
      // render bar/panel previews without touching anything when they have
      // not. Hand edits to the settings file land here too, via the watcher.
      applyTimer.restart()
    } else if (changed) {
      applyTimer.restart()
    }
  }

  // Theme switch: keep a theme-matched cursor in sync, or refresh preview
  // colors when Cursor Forge is not applied.
  onEffectiveColorChanged: if (settingsLoaded) applyTimer.restart()

  Timer {
    id: applyTimer
    interval: 350
    onTriggered: root.runGenerator(root.active)
  }

  FileView {
    path: root.settingsPath
    watchChanges: true
    printErrors: false
    onLoaded: root.adoptSettings(text())
    onFileChanged: reload()
    onLoadFailed: root.adoptSettings("")
  }

  Process {
    id: cursorPosQuery
    stdout: StdioCollector { id: cursorPosOut }
    onExited: function(exitCode) {
      if (exitCode !== 0) return
      var parts = String(cursorPosOut.text).trim().split(",")
      if (parts.length < 2) return
      var x = Number(parts[0])
      var y = Number(parts[1])
      if (isFinite(x) && isFinite(y)) root.ripple(x, y)
    }
  }

  Process {
    id: generator
    stdout: StdioCollector { id: generatorOut }
    stderr: StdioCollector { id: generatorErr }
    onExited: function(exitCode) {
      if (exitCode === 127) {
        root.lastError = "Cursor Forge needs /usr/bin/python3"
      } else {
        root.handleResult(generatorOut.text)
      }
      if (root.pendingReset) {
        root.pendingReset = false
        root.pendingApply = false
        root.runReset()
      } else if (root.pendingApply) {
        root.pendingApply = false
        root.runGenerator(root.active)
      }
    }
  }

  IpcHandler {
    target: root.pluginId

    function status(): string {
      return JSON.stringify({
        style: root.style,
        colorMode: root.colorMode,
        customColor: root.customColor,
        effectiveColor: root.effectiveColor,
        imagePath: root.imagePath,
        imageHotspot: root.imageHotspot,
        size: root.cursorSize,
        leftHanded: root.leftHanded,
        animated: root.animated,
        motion: root.motion,
        mode: root.mode,
        speed: root.speed,
        rippleShape: root.rippleShape,
        clickRipple: root.clickRipple,
        active: root.active,
        busy: root.busy,
        lastError: root.lastError,
        settingsPath: root.settingsPath
      })
    }

    function apply(): string { root.requestApply(); return "ok" }
    function reset(): string { root.runReset(); return "ok" }
    function cycle(): string { root.cycleStyle(); return "ok" }
    function matchTheme(): string { root.setColorMode("theme"); return "ok" }

    function setStyle(name: string): string {
      return root.setStyle(name) ? "ok" : "unknown style"
    }

    function setColor(hex: string): string {
      return root.setCustomColor(hex) ? "ok" : "invalid color; expected #rrggbb"
    }

    function setImage(path: string): string {
      return root.setImagePath(path) ? "ok" : "expected an absolute file path"
    }

    function setImageHotspot(spot: string): string {
      return root.setImageHotspot(spot) ? "ok" : "expected x,y within 0-23"
    }

    function toggleLeftHanded(): string {
      root.setLeftHanded(!root.leftHanded)
      return root.leftHanded ? "left" : "right"
    }

    function toggleAnimation(): string {
      root.setAnimated(!root.animated)
      return root.animated ? "animated" : "static"
    }

    function click(): string { return root.triggerRipple() }

    function toggleClickRipple(): string {
      root.setClickRipple(!root.clickRipple)
      return root.clickRipple ? "on" : "off"
    }

    function toggleMotion(): string {
      root.setMotion(!root.motion)
      return root.motion ? "moving" : "still"
    }

    function setMode(name: string): string {
      return root.setMode(name) ? "ok" : "expected static|glints|full"
    }

    function setSpeed(name: string): string {
      return root.setSpeed(name) ? "ok" : "expected calm|normal|lively"
    }

    function setRippleShape(name: string): string {
      return root.setRippleShape(name) ? "ok" : "expected diamond|circle|burst"
    }
  }
}
