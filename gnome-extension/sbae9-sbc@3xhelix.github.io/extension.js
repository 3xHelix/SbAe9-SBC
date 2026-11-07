// SPDX-License-Identifier: GPL-2.0-only
// Sound Blaster AE-9 in GNOME's top bar: the card's basics, through
// `sbae9-sbc ctl` (Sound Blaster Command for Linux), so every change follows
// the app's rules (two-stage SBX, rate cap per mode, quantum floor,
// bit-depth reopen). The same as the KDE panel widget (../plasmoid).

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import * as Dialog from 'resource:///org/gnome/shell/ui/dialog.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BIN = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'sbae9-sbc']);
const POLL_OPEN = 2;      // seconds, while the menu is open
const POLL_CLOSED = 10;

const PHANTOM_WARNING =
    'Phantom power puts 48 V on the head unit\'s XLR/TRS jack. It can damage some ' +
    'equipment (ribbon mics, some line-level sources). Only turn it on for ' +
    'condenser mics that need it.';

const khz = r => `${r / 1000} kHz`;

// the keyboard shortcuts (settings keys) and what each toggles
const SHORTCUTS = {'toggle-direct': 'direct', 'toggle-output': 'output', 'toggle-sbx': 'sbx'};

// GNOME's on-screen popup (as the volume keys'), on the monitor in use
function osd(text, iconName) {
    const icon = Gio.ThemedIcon.new(iconName);
    const monitor = global.display.get_current_monitor();
    const m = Main.osdWindowManager;
    if (typeof m.showOne === 'function')
        m.showOne(monitor, icon, text, null);       // GNOME 50
    else
        m.show(monitor, icon, text);                // GNOME 45-49
}

function confirmPhantom(onYes) {
    const dialog = new ModalDialog.ModalDialog({styleClass: 'modal-dialog'});
    dialog.contentLayout.add_child(new Dialog.MessageDialogContent({
        title: 'Turn on phantom power?',
        description: PHANTOM_WARNING,
    }));
    dialog.setButtons([
        {label: 'Cancel', action: () => dialog.close(), key: Clutter.KEY_Escape, default: true},
        {label: 'Turn on', action: () => { dialog.close(); onYes(); }},
    ]);
    dialog.open();
}

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init(ext) {
        super._init(0.5, 'Sound Blaster AE-9');
        this._ext = ext;
        this._st = {};
        this._pending = 0;
        this._cancel = new Gio.Cancellable();
        this._timer = 0;
        this._settle = 0;
        this._syncing = false;     // switches set from the card, not clicked
        this._settings = ext.getSettings();
        this._settingsId = this._settings.connect('changed', () => this._update());

        const box = new St.BoxLayout({style_class: 'panel-status-menu-box'});
        this._icon = new St.Icon({icon_name: 'audio-card-symbolic', style_class: 'system-status-icon'});
        this._rate = new St.Label({text: '', y_align: Clutter.ActorAlign.CENTER, style_class: 'sbae9-rate'});
        box.add_child(this._icon);
        box.add_child(this._rate);
        this.add_child(box);

        this._build();
        this.menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refresh();
            this._schedule(open ? POLL_OPEN : POLL_CLOSED);
        });
        this._refresh();
        this._schedule(POLL_CLOSED);
    }

    // --- running sbae9-sbc ctl --------------------------------------------
    _run(args, done) {
        let proc;
        try {
            proc = Gio.Subprocess.new([BIN, 'ctl', ...args],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
        } catch (e) {
            done(null);
            return;
        }
        proc.communicate_utf8_async(null, this._cancel, (p, res) => {
            let out = null;
            try {
                const [, stdout] = p.communicate_utf8_finish(res);
                out = JSON.parse(stdout);
            } catch (e) {
                if (e.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                    return;
                out = null;
            }
            done(out);
        });
    }

    _refresh() {
        this._run(['status'], st => {
            this._st = st ?? {present: false, missing: true};
            this._update();
        });
    }

    _change(...args) {
        this._error('');
        this._pending++;
        this._run(args, res => {
            this._pending = Math.max(0, this._pending - 1);
            if (!res)
                this._error('sbae9-sbc didn\'t answer (is Sound Blaster Command installed?)');
            else if (!res.ok)
                this._error(res.error);
            this._refresh();
            // the card and PipeWire take a moment to follow
            if (this._settle)
                GLib.source_remove(this._settle);
            this._settle = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1200, () => {
                this._settle = 0;
                this._refresh();
                return GLib.SOURCE_REMOVE;
            });
        });
    }

    _schedule(secs) {
        if (this._timer)
            GLib.source_remove(this._timer);
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, secs, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    // --- menu ---------------------------------------------------------------
    _build() {
        const m = this.menu;
        this._title = new PopupMenu.PopupMenuItem('Sound Blaster AE-9', {reactive: false});
        this._title.label.add_style_class_name('popup-subtitle-menu-item');
        m.addMenuItem(this._title);
        this._missing = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._missing.label.clutter_text.line_wrap = true;
        m.addMenuItem(this._missing);

        this._card = new PopupMenu.PopupMenuSection();
        m.addMenuItem(this._card);

        // DSP / Direct (two stages, as in the app: DSP first, then SBX)
        this._dsp = new PopupMenu.PopupMenuItem('DSP (SBX, EQ, speaker setup)');
        this._dsp.connect('activate', () => this._change('direct', '0'));
        this._direct = new PopupMenu.PopupMenuItem('Direct Mode (straight to the DAC)');
        this._direct.connect('activate', () => this._change('direct', '1'));
        this._card.addMenuItem(this._direct);
        this._card.addMenuItem(this._dsp);

        this._sbx = new PopupMenu.PopupSwitchMenuItem('SBX', false);
        this._sbx.connect('toggled', (_i, on) => {
            if (!this._syncing)
                this._change('sbx', on ? '1' : '0');
        });
        this._card.addMenuItem(this._sbx);
        this._card.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._rateMenu = new PopupMenu.PopupSubMenuMenuItem('Sample Rate');
        this._depthMenu = new PopupMenu.PopupSubMenuMenuItem('Bit Depth');
        this._quantumMenu = new PopupMenu.PopupSubMenuMenuItem('Quantum');
        this._card.addMenuItem(this._rateMenu);
        this._card.addMenuItem(this._depthMenu);
        this._card.addMenuItem(this._quantumMenu);
        this._lists = {};

        // the quick preset from the settings (rate and quantum at once)
        this._preset = new PopupMenu.PopupMenuItem('');
        this._preset.connect('activate', () => this._change('preset',
            String(this._settings.get_int('quick-rate')), String(this._settings.get_int('quick-quantum'))));
        this._card.addMenuItem(this._preset);

        this._now = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._now.label.add_style_class_name('sbae9-dim');
        this._now.label.clutter_text.line_wrap = true;
        this._card.addMenuItem(this._now);

        this._phantomSep = new PopupMenu.PopupSeparatorMenuItem();
        this._card.addMenuItem(this._phantomSep);
        // on only after the warning, off at once
        this._phantom = new PopupMenu.PopupSwitchMenuItem('Phantom Power 48V', false);
        this._phantom.connect('toggled', (item, on) => {
            if (this._syncing)
                return;
            if (!on) {
                this._change('phantom', '0');
                return;
            }
            this._quiet(() => item.setToggleState(false));
            this.menu.close();
            confirmPhantom(() => this._change('phantom', '1'));
        });
        this._card.addMenuItem(this._phantom);

        this._err = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._err.label.add_style_class_name('sbae9-error');
        this._err.label.clutter_text.line_wrap = true;
        this._err.visible = false;
        m.addMenuItem(this._err);

        m.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const open = new PopupMenu.PopupMenuItem('Open Sound Blaster Command');
        open.connect('activate', () => {
            try {
                Gio.Subprocess.new([BIN], Gio.SubprocessFlags.NONE);
            } catch (e) {
                this._error('sbae9-sbc isn\'t installed: run Sound Blaster Command\'s install.sh.');
            }
        });
        m.addMenuItem(open);
    }

    _quiet(fn) {
        this._syncing = true;
        try {
            fn();
        } finally {
            this._syncing = false;
        }
    }

    _error(text) {
        this._err.label.text = text;
        this._err.visible = !!text;
    }

    // A submenu of choices; rebuilt only when its choices change, so an
    // open submenu isn't closed by the poll.
    _fill(sub, key, choices, current, pick) {
        const sig = JSON.stringify(choices);
        if (this._lists[key]?.sig !== sig) {
            sub.menu.removeAll();
            const items = choices.map(([text, value]) => {
                const it = new PopupMenu.PopupMenuItem(text);
                it.connect('activate', () => pick(value));
                sub.menu.addMenuItem(it);
                return [it, value];
            });
            this._lists[key] = {sig, items};
        }
        let shown = '';
        for (const [it, value] of this._lists[key].items) {
            const on = value === current;
            it.setOrnament(on ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
            if (on)
                shown = it.label.text.replace(/\s+\(.*\)$/, '');
        }
        return shown;
    }

    _update() {
        const st = this._st;
        const ready = st.present === true;
        this._missing.visible = !ready;
        this._missing.label.text = st.missing
            ? 'Sound Blaster Command (sbae9-sbc) isn\'t installed: run its install.sh.'
            : 'The AE-9 isn\'t there (driver not loaded?).';
        this._card.actor.visible = ready;
        const phantomOn = !!(st.phantom && st.phantom.on);
        if (phantomOn)
            this._icon.add_style_class_name('sbae9-phantom-on');
        else
            this._icon.remove_style_class_name('sbae9-phantom-on');
        const live = st.live ? st.live.rate : (st.rate_forced || 0);
        this._rate.text = !ready ? '' : live ? `${live / 1000}k` : '';
        if (!ready)
            return;

        this._dsp.setOrnament(st.direct ? PopupMenu.Ornament.NONE : PopupMenu.Ornament.CHECK);
        this._direct.setOrnament(st.direct ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        this._quiet(() => this._sbx.setToggleState(!!st.sbx));
        this._sbx.setSensitive(!!st.sbx_enabled);
        this._sbx.label.text = st.direct ? 'SBX — bypassed (Direct Mode)' : 'SBX';

        // sample rate: ones the card can't play now move to the nearest it can
        const play = st.playable || [];
        // the driver's rates, as many as the settings list, plus the one in force
        const want = this._settings.get_value('sample-rates').deepUnpack();
        const rates = [['Auto', 0], ...(st.rates || []).filter(r => want.includes(r) || r === st.rate_forced).map(r =>
            [khz(r) + (play.includes(r) ? '' : '  (not in this mode)'), r])];
        const rate = this._fill(this._rateMenu, 'rate', rates, st.rate_forced || 0,
            v => this._change('rate', String(v)));
        this._rateMenu.label.text = `Sample Rate: ${rate}`;

        const depths = st.depths || [];
        if (depths.length) {
            const d = this._fill(this._depthMenu, 'depth', depths.map((t, i) => [t, i]), st.depth,
                v => this._change('depth', String(v)));
            this._depthMenu.label.text = `Bit Depth: ${d}`;
            this._depthMenu.setSensitive(true);
        } else {
            this._depthMenu.label.text = `Bit Depth: ${st.depth_fixed || '24-bit'}`;
            this._depthMenu.setSensitive(false);
        }

        // the settings' list, plus the pick in force
        const qs = this._settings.get_value('quantum-values').deepUnpack().filter(x => x > 0);
        if (st.quantum_pick && !qs.includes(st.quantum_pick))
            qs.push(st.quantum_pick);
        qs.sort((a, b) => a - b);
        const quanta = [[`Auto (${st.quantum_default || 1024})`, 0], ...qs.map(x => [String(x), x])];
        const q = this._fill(this._quantumMenu, 'quantum', quanta, st.quantum_pick || 0,
            v => this._change('quantum', String(v)));
        this._quantumMenu.label.text = `Quantum: ${q}`;

        const qr = this._settings.get_int('quick-rate');
        const qq = this._settings.get_int('quick-quantum');
        this._preset.visible = qr > 0;
        this._preset.label.text = `Quick preset: ${khz(qr)} · quantum ${qq || 'Auto'}`;

        // what's running, and the latency
        const qn = st.quantum_forced || st.quantum_default || 0;
        const r = live || 48000;
        const bits = depths.length ? depths[st.depth] : st.depth_fixed;
        let now = st.live
            ? `Running: ${khz(st.live.rate)} · ${bits} · ${st.live.channels === 6 ? '5.1' : st.live.channels === 1 ? 'mono' : 'stereo'}`
            : 'Idle';
        if (qn)
            now += ` · latency ${(qn / r * 1000).toFixed(1)} ms`;
        if (st.quantum_pick && st.quantum_forced > st.quantum_pick)
            now += `\nQuantum raised to ${st.quantum_forced} for ${khz(st.rate_forced)} (no crackles).`;
        if (this._pending)
            now += '\nApplying…';
        this._now.label.text = now;

        const ph = st.phantom;
        this._phantomSep.visible = this._phantom.visible = !!ph;
        if (ph) {
            this._quiet(() => this._phantom.setToggleState(phantomOn));
            this._phantom.setSensitive(!!ph.writable);
            this._phantom.label.text = ph.writable ? 'Phantom Power 48V'
                : 'Phantom Power 48V (head unit button)';
            if (phantomOn)
                this._phantom.label.add_style_class_name('sbae9-phantom-on');
            else
                this._phantom.label.remove_style_class_name('sbae9-phantom-on');
        }
    }

    // A keyboard shortcut: toggle, then say how it left things on screen.
    shortcut(cmd) {
        const st = this._st;
        this._run([cmd, 'toggle'], res => {
            if (!res) {
                osd('Sound Blaster Command isn\'t installed', 'dialog-error-symbolic');
            } else if (!res.ok) {
                osd(res.error, 'dialog-warning-symbolic');
            } else if (cmd === 'direct') {
                osd(st.direct ? 'DSP on' : 'Direct Mode on', 'audio-card-symbolic');
            } else if (cmd === 'sbx') {
                osd(st.sbx ? 'SBX off' : 'SBX on', 'audio-card-symbolic');
            } else {
                const hp = st.output !== 'headphones';
                osd(hp ? 'Headphones' : 'Speakers', hp ? 'audio-headphones-symbolic' : 'audio-speakers-symbolic');
            }
            this._refresh();
        });
    }

    destroy() {
        if (this._settingsId)
            this._settings.disconnect(this._settingsId);
        this._settingsId = 0;
        this._cancel.cancel();
        if (this._timer)
            GLib.source_remove(this._timer);
        if (this._settle)
            GLib.source_remove(this._settle);
        this._timer = this._settle = 0;
        super.destroy();
    }
});

export default class SbAe9Extension extends Extension {
    enable() {
        this._indicator = new Indicator(this);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
        // the shortcuts, no keys by default (set in the preferences)
        this._keys = this.getSettings();
        for (const [name, cmd] of Object.entries(SHORTCUTS)) {
            Main.wm.addKeybinding(name, this._keys, Meta.KeyBindingFlags.NONE,
                Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
                () => this._indicator?.shortcut(cmd));
        }
    }

    disable() {
        for (const name of Object.keys(SHORTCUTS))
            Main.wm.removeKeybinding(name);
        this._keys = null;
        this._indicator?.destroy();
        this._indicator = null;
    }
}
