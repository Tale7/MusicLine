"""Qt-side async wrapper around :mod:`translator`.

Network work runs on a single daemon worker thread. Results are delivered back
to the GUI thread through queued Qt signals, so the overlay never blocks while
a song is being translated and quitting the app is never held up by a pending
request.
"""

from __future__ import annotations

import queue
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from translator import config_signature, test_connection, translate_lines

_TRANSLATE = "translate"
_TEST = "test"


class TranslationController(QObject):
    # Full accumulated mapping {lyric_index: translated_text}, GUI thread.
    translations_ready = pyqtSignal(object)
    # Human readable backend error, GUI thread.
    status_message = pyqtSignal(str)
    # Result of the "Test Connection" button: (ok, detail), GUI thread.
    test_finished = pyqtSignal(bool, str)

    # Private signals emitted from the worker thread.
    _progress = pyqtSignal(int, object)
    _failed = pyqtSignal(int, str)
    _test_done = pyqtSignal(bool, str)

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.manager = settings_manager
        self._generation = 0
        self._lock = threading.Lock()
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._last_lyrics = []
        self._signature = None
        self._was_enabled = False

        self._queue = queue.Queue(maxsize=4)
        self._worker = threading.Thread(
            target=self._loop, name="kb-translate", daemon=True
        )
        self._worker.start()

        self._progress.connect(self._on_progress)
        self._failed.connect(self._on_failed)
        self._test_done.connect(self._on_test_done)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def config(self, override=None):
        source = override if override is not None else self.manager.settings
        keys = (
            "translation_enabled",
            "translation_engine",
            "translation_source",
            "translation_target",
            "ai_base_url",
            "ai_api_key",
            "ai_model",
        )
        defaults = {
            "translation_enabled": False,
            "translation_engine": "auto",
            "translation_source": "auto",
            "translation_target": "zh-Hans",
            "ai_base_url": "https://api.openai.com/v1",
            "ai_api_key": "",
            "ai_model": "gpt-4o-mini",
        }
        cfg = {}
        for key in keys:
            value = source.get(key, defaults[key])
            if value is None:
                value = defaults[key]
            cfg[key] = value
        return cfg

    def _enqueue(self, job):
        """Bounded queue: never let a burst of lyric updates pile up."""
        try:
            self._queue.put_nowait(job)
            return
        except queue.Full:
            pass
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            pass

    def submit_lyrics(self, lyrics_data):
        """Call whenever a new LRC timeline arrives (also with [] to clear)."""
        with self._lock:
            self._generation += 1
            generation = self._generation
            self._last_lyrics = list(lyrics_data or [])
        cfg = self.config()
        if not cfg["translation_enabled"] or not self._last_lyrics:
            self.translations_ready.emit({})
            return
        texts = [line.get("text", "") for line in self._last_lyrics]
        self._enqueue((_TRANSLATE, generation, texts, cfg))

    def apply_settings(self):
        """Re-read settings after Save; retranslate when anything semantic changed."""
        cfg = self.config()
        signature = config_signature(cfg)
        enabled = bool(cfg["translation_enabled"])
        semantic_changed = signature != self._signature
        if not semantic_changed and enabled == self._was_enabled:
            return
        if semantic_changed:
            with self._cache_lock:
                self._cache.clear()
        self._signature = signature
        self._was_enabled = enabled
        self.submit_lyrics(self._last_lyrics)

    def test_engine(self, override=None):
        """Run a one-line translation test using the given (possibly unsaved) settings."""
        self._enqueue((_TEST, self.config(override)))

    def start(self):
        """Initialise the cache signature and translate lyrics already loaded."""
        cfg = self.config()
        self._signature = config_signature(cfg)
        self._was_enabled = bool(cfg["translation_enabled"])
        self.submit_lyrics(self._last_lyrics)

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------
    def _loop(self):
        while True:
            job = self._queue.get()
            if job[0] == _TRANSLATE:
                _, generation, texts, cfg = job
                if self._is_cancelled(generation):
                    continue  # a newer track/settings already superseded this one
                self._run_translate(generation, texts, cfg)
            else:
                self._run_test(job[1])

    def _is_cancelled(self, generation):
        with self._lock:
            return generation != self._generation

    def _run_translate(self, generation, texts, cfg):
        def progress(mapping):
            if not self._is_cancelled(generation):
                self._progress.emit(generation, mapping)

        try:
            translate_lines(
                texts,
                cfg,
                self._cache,
                cache_lock=self._cache_lock,
                on_progress=progress,
                is_cancelled=lambda: self._is_cancelled(generation),
            )
        except Exception as exc:
            if not self._is_cancelled(generation):
                self._failed.emit(generation, str(exc))

    def _run_test(self, cfg):
        try:
            ok, detail = test_connection(cfg)
        except Exception as exc:  # defensive: never let the worker die silently
            ok, detail = False, str(exc)
        self._test_done.emit(ok, detail)

    # ------------------------------------------------------------------
    # GUI thread slots
    # ------------------------------------------------------------------
    def _on_progress(self, generation, mapping):
        with self._lock:
            if generation != self._generation:
                return
        self.translations_ready.emit(mapping)

    def _on_failed(self, generation, message):
        with self._lock:
            if generation != self._generation:
                return
        self.status_message.emit(message)

    def _on_test_done(self, ok, detail):
        self.test_finished.emit(ok, detail)
