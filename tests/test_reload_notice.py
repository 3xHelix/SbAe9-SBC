# SPDX-License-Identifier: GPL-2.0-only
"""ae9-reload's notice (driver 0.12.13+): while it reloads the driver the app
lets go of the card, then opens it again once the card is back."""

import os
import time

import support
from support import AppTestCase, process

from sbcommand import card as C
from sbcommand import window


def write_notice(text):
    with open(support.RELOAD_NOTICE, "w") as f:
        f.write(text)


def clear_notice():
    os.remove(support.RELOAD_NOTICE)


class NoticeTest(AppTestCase):
    def test_live_pid_counts(self):
        write_notice(f"{os.getpid()}\n")
        self.assertTrue(C.reload_notice_active())

    def test_dead_pid_is_stale(self):
        write_notice("999999999\n")
        self.assertFalse(C.reload_notice_active())

    def test_no_file(self):
        self.assertFalse(C.reload_notice_active())

    def test_empty_counts_for_a_while_only(self):
        write_notice("")
        self.assertTrue(C.reload_notice_active())
        old = time.time() - C.RELOAD_NOTICE_MAX_S - 5
        os.utime(support.RELOAD_NOTICE, (old, old))
        self.assertFalse(C.reload_notice_active())


class ReloadTest(AppTestCase):
    def start(self):
        write_notice(f"{os.getpid()}\n")
        self.ctx.card._check_notice()
        process()

    def test_lets_go_of_the_card(self):
        mixer = self.mixer
        closed = []
        mixer.close = lambda: closed.append(True)
        w = self.window()
        self.start()
        card = self.ctx.card
        self.assertTrue(closed)
        self.assertIsNone(card.mixer)
        self.assertTrue(card.reloading)
        self.assertTrue(card.answering)            # not an error
        self.assertIs(w.body.currentWidget(), w.no_card)
        self.assertEqual(w.no_card.title.text(), window.RELOADING_TITLE)
        self.assertFalse(w.no_card.steps_box.isVisible())
        self.assertEqual(w.no_card_bar.text(), window.RELOADING_BAR)

    def test_no_card_access_while_reloading(self):
        from sbcommand import alsa
        self.start()
        card = self.ctx.card
        looks = []
        real = alsa.find_card
        alsa.find_card = lambda *h: looks.append(h) or real(*h)
        try:
            card._try_open()
            card.retry()
            self.assertFalse(card.set(C.SBX, True))
        finally:
            alsa.find_card = real
        self.assertFalse(looks)
        self.assertIsNone(card.mixer)

    def test_reopens_once_the_card_is_back(self):
        w = self.window()
        w.go(3)
        self.start()
        card = self.ctx.card
        support.DRIVER["listed"] = False          # unloaded
        clear_notice()
        card._check_notice()
        self.assertFalse(card.reloading)
        process(50)
        self.assertIsNone(card.mixer)             # not back yet: waits
        support.DRIVER["listed"] = True
        card._check_notice()
        process(50)                               # the settle, then open
        self.assertIsNotNone(card.mixer)
        self.assertIs(w.body.currentWidget(), w.stack)
        self.assertEqual(w.stack.currentIndex(), 3)

    def test_killed_reload_releases_the_hold(self):
        self.start()
        write_notice("999999999\n")               # its PID died, the file stayed
        self.ctx.card._check_notice()
        process(50)
        self.assertFalse(self.ctx.card.reloading)
        self.assertIsNotNone(self.ctx.card.mixer)

    def test_reload_after_not_answering(self):
        card = self.ctx.card
        card._stopped_answering()
        process()
        self.start()
        clear_notice()
        card._check_notice()
        process(50)
        self.assertTrue(card.answering)
        self.assertIsNotNone(card.mixer)

    def test_polls_fast_enough(self):
        self.assertTrue(self.ctx.card._notice.isActive())
        self.assertLessEqual(self.ctx.card._notice.interval(), 500)

    def test_notice_at_start(self):
        write_notice(f"{os.getpid()}\n")
        from sbcommand.card import AE9
        card = AE9()
        try:
            self.assertTrue(card.reloading)
            self.assertIsNone(card.mixer)
        finally:
            card._notice.stop()
            card._retry.stop()
            card.deleteLater()
