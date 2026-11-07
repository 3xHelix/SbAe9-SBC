// SPDX-License-Identifier: GPL-2.0-only
// The AE-9's toggles as global shortcuts. Plasma's own "Keyboard Shortcuts"
// page holds one key, to open this widget; these live in System Settings
// (install.sh registers them, with no keys by default).

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
ColumnLayout {
    spacing: Kirigami.Units.largeSpacing

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: "Sound Blaster Command adds these to KDE's global shortcuts, with no keys set:"
    }

    Repeater {
        model: [
            ["Toggle Direct Mode / DSP", "Direct Mode on and off."],
            ["Toggle Speakers / Headphones", "The head unit's output."],
            ["Toggle SBX", "Needs Direct Mode off (DSP), as in the app."],
        ]
        RowLayout {
            required property var modelData
            Kirigami.Icon {
                source: "preferences-desktop-keyboard-shortcut"
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: Kirigami.Units.iconSizes.small
            }
            QQC2.Label { text: modelData[0]; font.bold: true }
            QQC2.Label { text: "— " + modelData[1]; opacity: 0.7 }
        }
    }

    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        opacity: 0.7
        text: "Set their keys in System Settings > Keyboard > Shortcuts, under "
              + "\"Sound Blaster Command\". Each press shows a short notification of what "
              + "changed. (The \"Keyboard Shortcuts\" page here is Plasma's own: one key "
              + "that opens this widget.)"
    }

    QQC2.Button {
        text: "Set Keys in System Settings…"
        icon.name: "configure-shortcuts"
        onClicked: KCMUtils.KCMLauncher.openSystemSettings("kcm_keys")
    }

    Item { Layout.fillHeight: true }
}
}
