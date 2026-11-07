// SPDX-License-Identifier: GPL-2.0-only
// Preferences: which sample rates and quantum values the menu lists, a quick
// preset, and the keyboard shortcuts (the same as the KDE widget's settings).

import Adw from 'gi://Adw';
import Gdk from 'gi://Gdk';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

const RATES = [44100, 48000, 88200, 96000, 176400, 192000, 384000];
const DEFAULT_QUANTA = [64, 128, 256, 512, 1024, 2048];
const Q_MIN = 8;
const Q_MAX = 8192;

const SHORTCUTS = [
    ['toggle-direct', 'Toggle Direct Mode / DSP', 'Direct Mode on and off'],
    ['toggle-output', 'Toggle Speakers / Headphones', 'The head unit\'s output'],
    ['toggle-sbx', 'Toggle SBX', 'Needs Direct Mode off (DSP), as in the app'],
];

// "64, 128 256" -> [64, 128, 256]; null if anything's off
function parseQuanta(text) {
    const out = [];
    for (const p of text.split(/[\s,]+/).filter(x => x)) {
        if (!/^\d+$/.test(p))
            return null;
        const n = parseInt(p);
        if (n < Q_MIN || n > Q_MAX)
            return null;
        if (!out.includes(n))
            out.push(n);
    }
    out.sort((a, b) => a - b);
    return out.length ? out : null;
}

// Waits for a key combination; Escape cancels, Backspace clears.
function captureShortcut(parent, title, done) {
    const dialog = new Adw.Window({
        modal: true, transient_for: parent, title, default_width: 420, default_height: 200,
    });
    const box = new Gtk.Box({
        orientation: Gtk.Orientation.VERTICAL, spacing: 12, valign: Gtk.Align.CENTER,
        margin_top: 24, margin_bottom: 24, margin_start: 24, margin_end: 24,
    });
    box.append(new Gtk.Label({label: `<b>${title}</b>`, use_markup: true}));
    box.append(new Gtk.Label({label: 'Press a key combination.\nEscape cancels, Backspace clears it.',
        justify: Gtk.Justification.CENTER}));
    dialog.set_content(box);

    const keys = new Gtk.EventControllerKey();
    keys.connect('key-pressed', (_c, keyval, keycode, state) => {
        const mods = state & Gtk.accelerator_get_default_mod_mask();
        if (!mods && keyval === Gdk.KEY_Escape) {
            dialog.close();
            return Gdk.EVENT_STOP;
        }
        if (!mods && keyval === Gdk.KEY_BackSpace) {
            done(null);
            dialog.close();
            return Gdk.EVENT_STOP;
        }
        if (!Gtk.accelerator_valid(keyval, mods))
            return Gdk.EVENT_STOP;          // a modifier alone: keep waiting
        done(Gtk.accelerator_name_with_keycode(null, keyval, keycode, mods));
        dialog.close();
        return Gdk.EVENT_STOP;
    });
    dialog.add_controller(keys);
    dialog.present();
}

export default class SbAe9Prefs extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        window._settings = settings;          // keep it alive with the window
        window.add(this._general(settings));
        window.add(this._shortcuts(settings, window));
    }

    _general(settings) {
        const page = new Adw.PreferencesPage({title: 'General', icon_name: 'preferences-system-symbolic'});

        // sample rates
        const rates = new Adw.PreferencesGroup({
            title: 'Sample Rates',
            description: 'The rates the menu lists. Rates your driver doesn\'t play are left out anyway; Auto is always there.',
        });
        for (const r of RATES) {
            const row = new Adw.SwitchRow({title: `${r / 1000} kHz`});
            row.active = settings.get_value('sample-rates').deepUnpack().includes(r);
            row.connect('notify::active', () => {
                let list = settings.get_value('sample-rates').deepUnpack().filter(x => x !== r);
                if (row.active)
                    list.push(r);
                list.sort((a, b) => a - b);
                settings.set_value('sample-rates', new GLib.Variant('ai', list));
            });
            rates.add(row);
        }
        page.add(rates);

        // quantum values
        const qGroup = new Adw.PreferencesGroup({
            title: 'Quantum Values',
            description: 'Frames per cycle; latency = quantum ÷ rate (256 at 48 kHz ≈ 5.3 ms). ' +
                '176.4 kHz and up raise it to 1024 (2048 at 384 kHz) so they don\'t crackle, ' +
                'and PipeWire caps it at its clock.max-quantum.',
        });
        const qRow = new Adw.EntryRow({
            title: `Values, ${Q_MIN} to ${Q_MAX}, separated by commas`,
            text: settings.get_value('quantum-values').deepUnpack().join(', '),
        });
        qRow.connect('changed', () => {
            const list = parseQuanta(qRow.text);
            if (list) {
                qRow.remove_css_class('error');
                settings.set_value('quantum-values', new GLib.Variant('ai', list));
            } else {
                qRow.add_css_class('error');
            }
        });
        const reset = new Gtk.Button({
            icon_name: 'edit-undo-symbolic', valign: Gtk.Align.CENTER,
            tooltip_text: 'Back to 64, 128, 256, 512, 1024, 2048', css_classes: ['flat'],
        });
        reset.connect('clicked', () => {
            settings.set_value('quantum-values', new GLib.Variant('ai', DEFAULT_QUANTA));
            qRow.text = DEFAULT_QUANTA.join(', ');
        });
        qRow.add_suffix(reset);
        qGroup.add(qRow);
        page.add(qGroup);

        // quick preset
        const pGroup = new Adw.PreferencesGroup({
            title: 'Quick Preset',
            description: 'Adds a menu entry that sets a sample rate and a quantum at once.',
        });
        const rateNames = ['No preset', ...RATES.map(r => `${r / 1000} kHz`)];
        const pRate = new Adw.ComboRow({title: 'Sample rate', model: Gtk.StringList.new(rateNames)});
        pRate.selected = Math.max(0, RATES.indexOf(settings.get_int('quick-rate')) + 1);
        pRate.connect('notify::selected', () =>
            settings.set_int('quick-rate', pRate.selected ? RATES[pRate.selected - 1] : 0));
        const pQuantum = new Adw.SpinRow({
            title: 'Quantum', subtitle: '0 = Auto',
            adjustment: new Gtk.Adjustment({lower: 0, upper: Q_MAX, step_increment: 32, page_increment: 256}),
        });
        pQuantum.value = settings.get_int('quick-quantum');
        pQuantum.connect('notify::value', () => settings.set_int('quick-quantum', Math.round(pQuantum.value)));
        const sync = () => { pQuantum.sensitive = pRate.selected > 0; };
        pRate.connect('notify::selected', sync);
        sync();
        pGroup.add(pRate);
        pGroup.add(pQuantum);
        page.add(pGroup);
        return page;
    }

    _shortcuts(settings, window) {
        const page = new Adw.PreferencesPage({title: 'Shortcuts', icon_name: 'input-keyboard-symbolic'});
        const group = new Adw.PreferencesGroup({
            title: 'Keyboard Shortcuts',
            description: 'None are set at first. Click one and press the keys. Each press shows ' +
                'what changed on screen.',
        });
        for (const [key, title, subtitle] of SHORTCUTS) {
            const row = new Adw.ActionRow({title, subtitle, activatable: true});
            const label = new Gtk.ShortcutLabel({disabled_text: 'Not set', valign: Gtk.Align.CENTER});
            const clear = new Gtk.Button({
                icon_name: 'edit-clear-symbolic', valign: Gtk.Align.CENTER,
                tooltip_text: 'Clear', css_classes: ['flat'],
            });
            const show = () => {
                const accel = settings.get_strv(key)[0] ?? '';
                label.accelerator = accel;
                clear.sensitive = accel !== '';
            };
            clear.connect('clicked', () => settings.set_strv(key, []));
            row.connect('activated', () => captureShortcut(window, title, accel =>
                settings.set_strv(key, accel ? [accel] : [])));
            settings.connect(`changed::${key}`, show);
            show();
            row.add_suffix(label);
            row.add_suffix(clear);
            group.add(row);
        }
        page.add(group);
        return page;
    }
}
