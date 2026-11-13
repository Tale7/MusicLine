"""JSON based internationalisation for MusicLine.

Drop a ``langs/<code>.json`` file into the langs folder and the language shows
up in the settings picker automatically. The English source text itself is the
lookup key, so a missing translation falls back to readable English instead of
an opaque identifier.
"""

import json
import locale
import os
import sys

LANGS_DIR = "langs"
AUTO_LANG = "auto"
FALLBACK_LANG = "en_US"


def resource_path(relative_path):
    """Resolve a data file both in dev mode and inside a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def langs_path():
    return resource_path(LANGS_DIR)


def _load_json(code):
    with open(os.path.join(langs_path(), code + ".json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def system_locale():
    """Best-effort OS UI language as a BCP-47-ish tag."""
    try:
        if sys.platform == "win32":
            import ctypes

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFFFF
            win_map = {
                0x0804: "zh_CN", 0x0404: "zh_TW", 0x0C04: "zh_HK",
                0x0411: "ja_JP", 0x0412: "ko_KR", 0x0407: "de_DE",
                0x040C: "fr_FR", 0x0410: "it_IT", 0x0C0A: "es_ES",
                0x0419: "ru_RU", 0x0416: "pt_BR",
            }
            if lcid in win_map:
                return win_map[lcid]
    except Exception:
        pass
    try:
        tag = locale.getlocale()[0]
        if tag:
            return tag.replace("-", "_")
    except Exception:
        pass
    return FALLBACK_LANG


class Translator:
    def __init__(self):
        self.code = FALLBACK_LANG
        self.display_name = "English"
        self.strings = {}
        self.fallback = {}
        self.set_language(AUTO_LANG)

    def available_languages(self):
        """Return [(code, native_name), ...] for every JSON file in langs/."""
        found = []
        directory = langs_path()
        if not os.path.isdir(directory):
            return found
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".json"):
                continue
            code = filename[:-5]
            try:
                meta = _load_json(code).get("_meta", {})
                found.append((code, meta.get("name", code)))
            except Exception:
                continue
        return found

    def _match(self, tag):
        codes = [code for code, _ in self.available_languages()]
        if tag in codes:
            return tag
        prefix = tag.split("_")[0].lower()
        for code in codes:
            if code.split("_")[0].lower() == prefix:
                return code
        if FALLBACK_LANG in codes:
            return FALLBACK_LANG
        return codes[0] if codes else FALLBACK_LANG

    def set_language(self, code):
        resolved = self._match(system_locale()) if code == AUTO_LANG else self._match(code)
        try:
            data = _load_json(resolved)
        except Exception:
            resolved = FALLBACK_LANG
            try:
                data = _load_json(resolved)
            except Exception:
                data = {}
        self.code = resolved
        self.strings = data.get("strings", {})
        self.display_name = data.get("_meta", {}).get("name", resolved)
        try:
            self.fallback = _load_json(FALLBACK_LANG).get("strings", {})
        except Exception:
            self.fallback = {}
        return resolved

    def tr(self, key, **kwargs):
        text = self.strings.get(key, self.fallback.get(key, key))
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text


_translator = Translator()


def tr(key, **kwargs):
    return _translator.tr(key, **kwargs)


def set_language(code):
    return _translator.set_language(code)


def available_languages():
    return _translator.available_languages()


def current_language():
    return _translator.code


def install_qt_translations(app, code=None):
    """Translate Qt's own dialogs (colour picker, standard buttons) using the
    qtbase_<lang>.qm files that PyInstaller already bundles. Return the
    translators so the caller can keep them alive."""
    installed = []
    try:
        from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
    except Exception:
        return installed
    tag = code or _translator.code
    candidates = []
    try:
        candidates.append(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    except Exception:
        pass
    candidates.append(resource_path(os.path.join("PyQt6", "Qt6", "translations")))
    for folder in candidates:
        if not folder:
            continue
        qt = QTranslator(app)
        if qt.load(QLocale(tag), "qtbase", "_", folder):
            app.installTranslator(qt)
            installed.append(qt)
            break
    return installed


def restart_application():
    """Restart after a language change so the tray menu and all widgets rebuild."""
    try:
        from PyQt6.QtCore import QProcess, QTimer
        from PyQt6.QtWidgets import QApplication

        if getattr(sys, "frozen", False):
            exe, args = sys.executable, sys.argv[1:]
        else:
            exe = sys.executable
            args = [os.path.abspath(sys.argv[0])] + sys.argv[1:]
        QProcess.startDetached(exe, args)
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(150, app.quit)
    except Exception as exc:
        print(f"[i18n] Could not restart: {exc}")
