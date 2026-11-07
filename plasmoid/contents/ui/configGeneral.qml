// SPDX-License-Identifier: GPL-2.0-only
// Widget settings: which sample rates and quantum values the popup lists,
// and an optional one-click preset.

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    id: page

    property var cfg_sampleRates: []
    property var cfg_quantumValues: []
    property int cfg_quickRate: 0
    property int cfg_quickQuantum: 0
    // Plasma also hands over the defaults; unused here, declared to keep it quiet
    property var cfg_sampleRatesDefault
    property var cfg_quantumValuesDefault
    property int cfg_quickRateDefault
    property int cfg_quickQuantumDefault

    readonly property var allRates: [44100, 48000, 88200, 96000, 176400, 192000, 384000]
    readonly property var defaultQuanta: [64, 128, 256, 512, 1024, 2048]
    readonly property int qMin: 8
    readonly property int qMax: 8192

    function hasRate(r) {
        return cfg_sampleRates.map(Number).indexOf(r) >= 0
    }

    function setRate(r, on) {
        var list = cfg_sampleRates.map(Number).filter(x => x !== r)
        if (on) list.push(r)
        list.sort((a, b) => a - b)
        cfg_sampleRates = list.map(String)
    }

    // "64, 128 256" -> [64, 128, 256]; null if anything's off
    function parseQuanta(text) {
        var parts = text.split(/[\s,]+/).filter(x => x !== "")
        var out = []
        for (var p of parts) {
            if (!/^\d+$/.test(p)) return null
            var n = parseInt(p)
            if (n < qMin || n > qMax) return null
            if (out.indexOf(n) < 0) out.push(n)
        }
        out.sort((a, b) => a - b)
        return out.length ? out : null
    }

    Kirigami.FormLayout {

    // --- sample rates ---------------------------------------------------
    ColumnLayout {
        Kirigami.FormData.label: "Sample rates:"
        spacing: 0
        Repeater {
            model: page.allRates
            QQC2.CheckBox {
                required property int modelData
                text: (modelData / 1000) + " kHz"
                checked: page.hasRate(modelData)
                onToggled: page.setRate(modelData, checked)
            }
        }
        QQC2.Label {
            text: "Rates your driver doesn't play are left out anyway. Auto is always there."
            wrapMode: Text.WordWrap
            opacity: 0.7
            font: Kirigami.Theme.smallFont
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
        }
    }

    Item { Kirigami.FormData.isSection: true }

    // --- quantum values -------------------------------------------------
    ColumnLayout {
        Kirigami.FormData.label: "Quantum values:"
        RowLayout {
            QQC2.TextField {
                id: quanta
                Layout.preferredWidth: Kirigami.Units.gridUnit * 16
                text: page.cfg_quantumValues.join(", ")
                placeholderText: "64, 128, 256, 512, 1024, 2048"
                onTextEdited: {
                    var list = page.parseQuanta(text)
                    if (list) page.cfg_quantumValues = list.map(String)
                }
            }
            QQC2.Button {
                text: "Reset"
                icon.name: "edit-undo"
                onClicked: {
                    page.cfg_quantumValues = page.defaultQuanta.map(String)
                    quanta.text = page.cfg_quantumValues.join(", ")
                }
            }
        }
        QQC2.Label {
            readonly property bool bad: quanta.text.trim() !== "" && page.parseQuanta(quanta.text) === null
            text: bad ? "Whole numbers from " + page.qMin + " to " + page.qMax + ", separated by commas."
                      : "Frames per cycle; latency = quantum ÷ rate (256 at 48 kHz ≈ 5.3 ms). "
                        + "176.4 kHz and up raise it to 1024 (2048 at 384 kHz) so they don't crackle, "
                        + "and PipeWire caps it at its clock.max-quantum."
            color: bad ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
            wrapMode: Text.WordWrap
            opacity: bad ? 1 : 0.7
            font: Kirigami.Theme.smallFont
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
        }
    }

    Item { Kirigami.FormData.isSection: true }

    // --- quick preset ---------------------------------------------------
    RowLayout {
        Kirigami.FormData.label: "Quick preset:"
        QQC2.ComboBox {
            id: quickRate
            textRole: "text"
            valueRole: "value"
            model: [{text: "No button", value: 0}].concat(
                       page.allRates.map(r => ({text: (r / 1000) + " kHz", value: r})))
            currentIndex: Math.max(0, indexOfValue(page.cfg_quickRate))
            onActivated: page.cfg_quickRate = currentValue
        }
        QQC2.Label { text: "with quantum"; enabled: page.cfg_quickRate > 0 }
        QQC2.SpinBox {
            enabled: page.cfg_quickRate > 0
            from: 0
            to: page.qMax
            stepSize: 32
            value: page.cfg_quickQuantum
            editable: true
            textFromValue: (v) => v === 0 ? "Auto" : v.toString()
            valueFromText: (t) => t.trim().toLowerCase() === "auto" ? 0 : parseInt(t) || 0
            onValueModified: page.cfg_quickQuantum = value
        }
    }
    QQC2.Label {
        text: "Adds a button to the popup that sets both at once."
        opacity: 0.7
        font: Kirigami.Theme.smallFont
    }
    }
}
