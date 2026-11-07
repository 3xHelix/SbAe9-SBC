// SPDX-License-Identifier: GPL-2.0-only
import QtQuick
import org.kde.plasma.configuration

ConfigModel {
    ConfigCategory {
        name: "General"
        icon: "configure"
        source: "configGeneral.qml"
    }
    ConfigCategory {
        name: "AE-9 Shortcuts"
        icon: "preferences-desktop-keyboard-shortcut"
        source: "configShortcuts.qml"
    }
}
