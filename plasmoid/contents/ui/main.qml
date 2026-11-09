// SPDX-License-Identifier: GPL-2.0-only
// Sound Blaster AE-9 panel widget: the card's basics, through
// `sbae9-sbc ctl` (Sound Blaster Command for Linux), so every change follows
// the app's rules: rate cap, quantum floor, bit-depth reopen, settings.

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PC
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var st: ({})            // the last `ctl status`
    property string error: ""
    property bool confirmPhantom: false
    property int pending: 0          // changes still running
    readonly property string bin: '"$HOME/.local/bin/sbae9-sbc"'
    readonly property bool ready: st.present === true

    Plasmoid.icon: "audio-card"
    toolTipMainText: "Sound Blaster AE-9"
    toolTipSubText: summary()

    function khz(r) { return (r / 1000).toString() + " kHz" }

    function liveRate() {
        return st.live ? st.live.rate : (st.rate_forced || 0)
    }

    function summary() {
        if (st.present === undefined) return "…"
        if (!ready) return "AE-9 not found"
        var parts = [st.direct ? "Direct Mode" : (st.sbx ? "DSP · SBX on" : "DSP · SBX off")]
        parts.push(st.live ? khz(st.live.rate) + (st.live.channels === 6 ? " · 5.1" : "") : "Idle")
        if (st.recording) parts.push("Recording")
        if (st.phantom && st.phantom.on) parts.push("Phantom 48V on")
        return parts.join("\n")
    }

    // --- the panel icon: the card (Breeze's audio-card outline, 22 x 22 grid)
    // with a DSP chip (Direct Mode off) or a bitstream (Direct Mode on),
    // green when idle, yellow while playing, red while recording
    readonly property var cardRects: [
        [2, 2, 1, 18],                      // bracket
        [3, 4, 17, 1], [3, 16, 17, 1], [19, 4, 1, 13],   // board
        [9, 17, 9, 1]                       // edge connector
    ]
    readonly property var chipRects: [
        [8, 7, 6, 7],                                   // the chip
        [6, 8, 2, 1], [6, 10, 2, 1], [6, 12, 2, 1],     // pins
        [14, 8, 2, 1], [14, 10, 2, 1], [14, 12, 2, 1],
        [9, 6, 1, 1], [12, 6, 1, 1], [9, 14, 1, 1], [12, 14, 1, 1]
    ]
    readonly property var bitsRects: [   // a square wave (a bitstream): 0 1 0 1 0 1
        [4, 13, 3, 1], [6, 8, 1, 6], [6, 8, 4, 1], [9, 8, 1, 6], [9, 13, 3, 1],
        [11, 8, 1, 6], [11, 8, 4, 1], [14, 8, 1, 6], [14, 13, 3, 1], [16, 8, 1, 6],
        [16, 8, 3, 1]
    ]
    readonly property color stateColor: !ready ? Kirigami.Theme.disabledTextColor
        : st.recording ? "#da4453" : st.playing ? "#fdbc4b" : "#27ae60"

    function stateText() {
        if (!ready) return ""
        return st.recording ? "Recording" : st.playing ? "Playing" : "Idle"
    }

    function shortRate() {
        if (!ready) return "—"
        var r = liveRate()
        return r ? (r / 1000).toString() + "k" : "AE9"
    }

    // --- running sbae9-sbc ctl --------------------------------------------
    P5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function (source, data) {
            disconnectSource(source)
            root.done(source, data["stdout"] || "")
        }
    }

    property int seq: 0
    function run(args) {
        // a unique tail, so the same command twice runs twice
        seq += 1
        exec.connectSource(bin + " ctl " + args + " # " + seq)
    }

    function refresh() { run("status") }

    function change(args) {
        error = ""
        pending += 1
        run(args)
    }

    function done(source, out) {
        var obj
        try { obj = JSON.parse(out) } catch (e) { obj = null }
        if (source.indexOf(" ctl status") >= 0) {
            if (obj) st = obj
            else if (st.present === undefined) st = {present: false, missing: true}
            return
        }
        pending = Math.max(0, pending - 1)
        if (!obj) error = "sbae9-sbc didn't answer (is Sound Blaster Command installed?)"
        else if (!obj.ok) error = obj.error
        refresh()
        settle.restart()      // the card and PipeWire take a moment to follow
    }

    Timer {
        id: poll
        interval: root.expanded ? 2000 : 10000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }
    Timer { id: settle; interval: 1200; onTriggered: root.refresh() }
    onExpandedChanged: function () {
        if (root.expanded) refresh()
        else confirmPhantom = false
    }

    function openApp() {
        exec.connectSource("setsid -f " + bin + " >/dev/null 2>&1 # " + (++seq))
        root.expanded = false
    }

    // --- panel icon --------------------------------------------------------
    compactRepresentation: MouseArea {
        Layout.minimumWidth: row.implicitWidth
        Layout.preferredWidth: row.implicitWidth
        onClicked: root.expanded = !root.expanded
        RowLayout {
            id: row
            anchors.fill: parent
            spacing: Kirigami.Units.smallSpacing
            Item {
                id: cardIcon
                Layout.fillHeight: true
                Layout.preferredWidth: height
                // whole pixels on the 22 grid where the panel allows it
                readonly property real side: Math.min(width, height)
                readonly property real u: side >= 22 ? Math.floor(side / 22) : side / 22
                Item {
                    width: 22 * cardIcon.u
                    height: 22 * cardIcon.u
                    anchors.centerIn: parent
                    Repeater {
                        model: root.cardRects.concat(root.st.direct ? root.bitsRects : root.chipRects)
                        Rectangle {
                            x: modelData[0] * cardIcon.u
                            y: modelData[1] * cardIcon.u
                            width: modelData[2] * cardIcon.u
                            height: modelData[3] * cardIcon.u
                            color: root.stateColor
                            antialiasing: false
                        }
                    }
                    // phantom power on: a red dot (the whole card used to turn red)
                    Rectangle {
                        visible: !!(root.st.phantom && root.st.phantom.on)
                        width: 7 * cardIcon.u
                        height: width
                        radius: width / 2
                        x: 15 * cardIcon.u
                        y: 15 * cardIcon.u
                        color: "#da4453"
                        border.color: Kirigami.Theme.backgroundColor
                        border.width: Math.max(1, cardIcon.u)
                    }
                }
            }
            PC.Label {
                text: root.shortRate()
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                Layout.alignment: Qt.AlignVCenter
            }
        }
    }

    // --- popup -----------------------------------------------------------
    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.minimumWidth: Kirigami.Units.gridUnit * 17
        spacing: Kirigami.Units.smallSpacing

        RowLayout {
            Layout.fillWidth: true
            Kirigami.Heading { text: "Sound Blaster AE-9"; level: 3; Layout.fillWidth: true }
            PC.BusyIndicator {
                running: root.pending > 0
                visible: running
                Layout.preferredHeight: Kirigami.Units.iconSizes.small
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
            }
            PC.ToolButton {
                icon.name: "configure"
                onClicked: root.openApp()
                PC.ToolTip { text: "Open Sound Blaster Command" }
            }
        }

        PC.Label {
            visible: !root.ready
            text: root.st.missing ? "Sound Blaster Command (sbae9-sbc) isn't installed: run its install.sh."
                                  : root.st.present === false ? "The AE-9 isn't there (driver not loaded?)." : "…"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        GridLayout {
            visible: root.ready
            columns: 2
            columnSpacing: Kirigami.Units.largeSpacing
            rowSpacing: Kirigami.Units.smallSpacing
            Layout.fillWidth: true

            // DSP / Direct
            PC.Label { text: "Mode" }
            RowLayout {
                spacing: 0
                PC.Button {
                    text: "Direct"
                    checkable: true
                    checked: root.st.direct === true
                    onClicked: { checked = Qt.binding(() => root.st.direct === true); root.change("direct 1") }
                }
                PC.Button {
                    id: dspBtn
                    text: "DSP"
                    checkable: true
                    checked: root.st.direct === false
                    onClicked: { checked = Qt.binding(() => root.st.direct === false); root.change("direct 0") }
                }
                Item { Layout.fillWidth: true }
            }

            PC.Label { text: "SBX" }
            PC.Switch {
                checked: !!root.st.sbx
                enabled: !!root.st.sbx_enabled
                // two stages, as in the app: DSP first, then SBX on/off
                text: root.st.direct ? "Bypassed (Direct Mode)" : (root.st.sbx ? "On" : "Off")
                onToggled: { var on = checked; checked = Qt.binding(() => !!root.st.sbx); root.change("sbx " + (on ? 1 : 0)) }
            }

            // sample rate: Auto + the rates the driver offers; ones the card
            // can't play right now move to the nearest it can (as in the app)
            PC.Label { text: "Sample Rate" }
            PC.ComboBox {
                id: rateBox
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 11
                textRole: "text"
                valueRole: "value"
                model: {
                    var m = [{text: "Auto", value: 0}]
                    var play = root.st.playable || []
                    // the driver's rates, as many as the settings list, plus the one in force
                    var want = Plasmoid.configuration.sampleRates.map(Number)
                    for (var r of (root.st.rates || []).filter(x => want.indexOf(x) >= 0 || x === root.st.rate_forced))
                        m.push({text: root.khz(r) + (play.indexOf(r) < 0 ? "  (not in this mode)" : ""), value: r})
                    return m
                }
                currentIndex: Math.max(0, indexOfValue(root.st.rate_forced || 0))
                onActivated: function (i) {
                    var v = valueAt(i)
                    currentIndex = Qt.binding(() => Math.max(0, indexOfValue(root.st.rate_forced || 0)))
                    root.change("rate " + v)
                }
            }

            PC.Label { text: "Bit Depth" }
            PC.ComboBox {
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 11
                enabled: (root.st.depths || []).length > 0
                model: (root.st.depths || []).length ? root.st.depths : [root.st.depth_fixed || "24-bit"]
                currentIndex: root.st.depth || 0
                onActivated: function (i) {
                    currentIndex = Qt.binding(() => root.st.depth || 0)
                    root.change("depth " + i)
                }
            }

            PC.Label { text: "Quantum" }
            PC.ComboBox {
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 11
                textRole: "text"
                valueRole: "value"
                model: {
                    var m = [{text: "Auto (" + (root.st.quantum_default || 1024) + ")", value: 0}]
                    // the settings' list, plus the pick in force
                    var qs = Plasmoid.configuration.quantumValues.map(Number).filter(x => x > 0)
                    if (root.st.quantum_pick && qs.indexOf(root.st.quantum_pick) < 0) qs.push(root.st.quantum_pick)
                    qs.sort((a, b) => a - b)
                    for (var q of qs) m.push({text: q.toString(), value: q})
                    return m
                }
                currentIndex: Math.max(0, indexOfValue(root.st.quantum_pick || 0))
                onActivated: function (i) {
                    var v = valueAt(i)
                    currentIndex = Qt.binding(() => Math.max(0, indexOfValue(root.st.quantum_pick || 0)))
                    root.change("quantum " + v)
                }
            }
        }

        // the quick preset from the settings, as the pw widget's button
        PC.Button {
            readonly property int qr: Plasmoid.configuration.quickRate
            readonly property int qq: Plasmoid.configuration.quickQuantum
            visible: root.ready && qr > 0
            text: (qr / 1000) + " kHz · " + (qq ? qq : "Auto")
            icon.name: "media-playback-start"
            onClicked: root.change("preset " + qr + " " + qq)
            PC.ToolTip { text: "Quick preset: sample rate and quantum at once (set in the widget's settings)" }
        }

        // what's running, and the latency
        PC.Label {
            visible: root.ready
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            opacity: 0.75
            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
            text: {
                var s = root.st
                if (!root.ready) return ""
                var q = s.quantum_forced || s.quantum_default || 0
                var rate = root.liveRate() || 48000
                var lat = q ? " · latency " + (q / rate * 1000).toFixed(1) + " ms" : ""
                var bits = (s.depths || []).length ? s.depths[s.depth] : s.depth_fixed
                var now = s.live ? "Running: " + root.khz(s.live.rate) + " · " + bits + " · "
                                   + (s.live.channels === 6 ? "5.1" : s.live.channels === 1 ? "mono" : "stereo")
                                 : "Idle"
                var raised = s.quantum_pick && s.quantum_forced > s.quantum_pick
                             ? "\nQuantum raised to " + s.quantum_forced + " for " + root.khz(s.rate_forced) + " (no crackles)." : ""
                return now + lat + raised
            }
        }

        // phantom power: on only after the warning, off at once
        Kirigami.Separator { visible: root.ready && !!root.st.phantom; Layout.fillWidth: true }
        RowLayout {
            visible: root.ready && !!root.st.phantom
            Layout.fillWidth: true
            PC.Label {
                text: "Phantom Power 48V"
                color: root.st.phantom && root.st.phantom.on ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                font.bold: !!(root.st.phantom && root.st.phantom.on)
                Layout.fillWidth: true
            }
            PC.Switch {
                checked: !!(root.st.phantom && root.st.phantom.on)
                enabled: !!(root.st.phantom && root.st.phantom.writable)
                onToggled: {
                    var on = checked
                    checked = Qt.binding(() => !!(root.st.phantom && root.st.phantom.on))
                    if (on) root.confirmPhantom = true
                    else { root.confirmPhantom = false; root.change("phantom 0") }
                }
            }
        }
        PC.Label {
            visible: root.ready && !!root.st.phantom && !root.st.phantom.writable
            text: "Switched with the head unit's button (this driver can't switch it)."
            wrapMode: Text.WordWrap
            opacity: 0.75
            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
            Layout.fillWidth: true
        }
        Rectangle {
            visible: root.confirmPhantom
            Layout.fillWidth: true
            implicitHeight: warn.implicitHeight + 2 * Kirigami.Units.smallSpacing
            radius: Kirigami.Units.smallSpacing
            color: Qt.rgba(Kirigami.Theme.negativeTextColor.r, Kirigami.Theme.negativeTextColor.g, Kirigami.Theme.negativeTextColor.b, 0.15)
            border.color: Kirigami.Theme.negativeTextColor
            ColumnLayout {
                id: warn
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                PC.Label {
                    text: "Phantom power puts 48 V on the head unit's XLR/TRS jack. It can damage some "
                          + "equipment (ribbon mics, some line-level sources). Only turn it on for "
                          + "condenser mics that need it."
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    Item { Layout.fillWidth: true }
                    PC.Button { text: "Cancel"; onClicked: root.confirmPhantom = false }
                    PC.Button {
                        text: "Turn on"
                        icon.name: "dialog-warning"
                        onClicked: { root.confirmPhantom = false; root.change("phantom 1") }
                    }
                }
            }
        }

        PC.Label {
            visible: root.error !== ""
            text: root.error
            color: Kirigami.Theme.negativeTextColor
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Item { Layout.fillHeight: true }      // keeps it all at the top
    }
}
