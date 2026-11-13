"""Lyrics translation backends for MusicLine.

Design goals
------------
* One built-in, free, keyless engine chain: Microsoft Bing -> Google -> MyMemory.
  (Baidu Translate is deliberately NOT supported anywhere in this module.)
* An optional user-supplied OpenAI-compatible AI endpoint (OpenAI, DeepSeek,
  Moonshot, Ollama, LM Studio, one-api, ...).
* Batch translation so a whole song costs a handful of requests instead of one
  request per lyric line, plus an in-memory cache keyed by (config, source text).
* Pure-Python, no Qt imports: everything here is safe to call from a worker
  thread. The Qt-facing async wrapper lives in translation_controller.py.

The public entry point is ``translate_lines()``.
"""

from __future__ import annotations

import json
import re
import threading
import time

import requests

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
}

TIMEOUT_FREE = 12
TIMEOUT_AI = 45
CHUNK_SIZE = 20
MYMEMORY_BUDGET = 25  # anonymous quota is small; only use it as a last resort


class TranslationError(Exception):
    """Raised when every configured engine failed for a batch of lines."""


# id -> display name (native) -> per-provider language codes / AI description
LANGUAGES = [
    {"id": "auto",    "name": "Auto detect",       "bing": "auto-detect", "google": "auto", "mymemory": "en",      "ai": "the source language (detect automatically)"},
    {"id": "zh-Hans", "name": "简体中文",           "bing": "zh-Hans",     "google": "zh-CN",  "mymemory": "zh-CN",   "ai": "Simplified Chinese"},
    {"id": "zh-Hant", "name": "繁體中文",           "bing": "zh-Hant",     "google": "zh-TW",  "mymemory": "zh-TW",   "ai": "Traditional Chinese"},
    {"id": "en",      "name": "English",           "bing": "en",          "google": "en",     "mymemory": "en",      "ai": "English"},
    {"id": "ja",      "name": "日本語",             "bing": "ja",          "google": "ja",     "mymemory": "ja",      "ai": "Japanese"},
    {"id": "ko",      "name": "한국어",             "bing": "ko",          "google": "ko",     "mymemory": "ko",      "ai": "Korean"},
    {"id": "fr",      "name": "Français",          "bing": "fr",          "google": "fr",     "mymemory": "fr",      "ai": "French"},
    {"id": "de",      "name": "Deutsch",           "bing": "de",          "google": "de",     "mymemory": "de",      "ai": "German"},
    {"id": "es",      "name": "Español",           "bing": "es",          "google": "es",     "mymemory": "es",      "ai": "Spanish"},
    {"id": "ru",      "name": "Русский",           "bing": "ru",          "google": "ru",     "mymemory": "ru",      "ai": "Russian"},
    {"id": "pt",      "name": "Português",         "bing": "pt",          "google": "pt",     "mymemory": "pt",      "ai": "Portuguese"},
    {"id": "it",      "name": "Italiano",          "bing": "it",          "google": "it",     "mymemory": "it",      "ai": "Italian"},
    {"id": "ar",      "name": "العربية",            "bing": "ar",          "google": "ar",     "mymemory": "ar",      "ai": "Arabic"},
    {"id": "th",      "name": "ไทย",               "bing": "th",          "google": "th",     "mymemory": "th",      "ai": "Thai"},
    {"id": "vi",      "name": "Tiếng Việt",        "bing": "vi",          "google": "vi",     "mymemory": "vi",      "ai": "Vietnamese"},
    {"id": "id",      "name": "Bahasa Indonesia",  "bing": "id",          "google": "id",     "mymemory": "id",      "ai": "Indonesian"},
    {"id": "tr",      "name": "Türkçe",            "bing": "tr",          "google": "tr",     "mymemory": "tr",      "ai": "Turkish"},
    {"id": "nl",      "name": "Nederlands",        "bing": "nl",          "google": "nl",     "mymemory": "nl",      "ai": "Dutch"},
    {"id": "pl",      "name": "Polski",            "bing": "pl",          "google": "pl",     "mymemory": "pl",      "ai": "Polish"},
    {"id": "sv",      "name": "Svenska",           "bing": "sv",          "google": "sv",     "mymemory": "sv",      "ai": "Swedish"},
    {"id": "uk",      "name": "Українська",        "bing": "uk",          "google": "uk",     "mymemory": "uk",      "ai": "Ukrainian"},
    {"id": "hi",      "name": "हिन्दी",              "bing": "hi",          "google": "hi",     "mymemory": "hi",      "ai": "Hindi"},
    {"id": "el",      "name": "Ελληνικά",          "bing": "el",          "google": "el",     "mymemory": "el",      "ai": "Greek"},
    {"id": "he",      "name": "עברית",             "bing": "he",          "google": "iw",     "mymemory": "he",      "ai": "Hebrew"},
]

LANG_BY_ID = {lang["id"]: lang for lang in LANGUAGES}

# (id, English label used as an i18n key)
ENGINES = [
    ("auto", "Built-in (Bing > Google > MyMemory)"),
    ("bing", "Microsoft Bing (free, no key)"),
    ("google", "Google Translate (free, no key)"),
    ("mymemory", "MyMemory (free, no key)"),
    ("ai", "Custom AI API"),
]


def _lang(value, provider):
    return LANG_BY_ID.get(value, LANG_BY_ID["en"])[provider]


def _ai_lang(value):
    return LANG_BY_ID.get(value, LANG_BY_ID["en"])["ai"]


def config_signature(cfg):
    """Anything that changes the meaning of a translation belongs here."""
    return (
        cfg.get("translation_engine", "auto"),
        cfg.get("translation_source", "auto"),
        cfg.get("translation_target", "zh-Hans"),
        (cfg.get("ai_base_url") or "").strip().rstrip("/"),
        (cfg.get("ai_model") or "").strip(),
    )


def is_translatable(text):
    """Skip blank lines, '...' intro markers and purely numeric/punctuation lines."""
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if not re.search(r"[^\W\d_]", stripped, re.UNICODE):
        return False
    return True


# ---------------------------------------------------------------------------
# Free engine: Microsoft Bing (web translator endpoint, no API key)
# ---------------------------------------------------------------------------
class BingTranslator:
    id = "bing"
    label = "Bing"
    HOSTS = ("https://cn.bing.com", "https://www.bing.com")

    def __init__(self):
        self._lock = threading.Lock()
        self._session = None
        self._params = None

    def _bootstrap(self):
        last_error = None
        for host in self.HOSTS:
            try:
                session = requests.Session()
                session.headers.update(_UA)
                session.headers["Referer"] = host + "/translator"
                session.headers["X-Requested-With"] = "XMLHttpRequest"
                resp = session.get(host + "/translator", timeout=TIMEOUT_FREE)
                resp.raise_for_status()
                html = resp.text
                ig = re.search(r'IG\s*[=:]\s*"([0-9A-Fa-f]{32})"', html)
                iid = re.search(r'data-iid="([^"]+)"', html)
                abuse = re.search(
                    r"params_AbusePreventionHelper\s*=\s*\[([^\]]+)\]", html
                )
                if not (ig and abuse):
                    raise TranslationError("Bing page layout changed")
                keys = re.findall(r"(\d{10,})", abuse.group(1))
                tokens = re.findall(r'"([^"]+)"', abuse.group(1))
                params = {
                    "host": host,
                    "ig": ig.group(1),
                    "iid": iid.group(1) if iid else "translator.5023",
                    "key": keys[0] if keys else "",
                    "token": tokens[0] if tokens else "",
                }
                return session, params
            except Exception as exc:  # try the next edge host
                last_error = exc
        raise TranslationError("Bing is unreachable: %s" % last_error)

    def _post(self, session, params, text, source, target):
        url = "%s/ttranslatev3?isVertical=1&IG=%s&IID=%s" % (
            params["host"], params["ig"], params["iid"]
        )
        payload = {
            "fromLang": _lang(source, "bing"),
            "to": _lang(target, "bing"),
            "text": text,
            "token": params["token"],
            "key": params["key"],
        }
        resp = session.post(url, data=payload, timeout=TIMEOUT_FREE)
        resp.raise_for_status()
        if not resp.text.strip():
            raise TranslationError("Bing returned an empty response")
        data = resp.json()
        return data[0]["translations"][0]["text"]

    def translate(self, texts, source, target, cfg=None):
        with self._lock:
            if self._session is None:
                self._session, self._params = self._bootstrap()
            out = []
            for text in texts:
                translated = None
                for attempt in range(2):
                    try:
                        translated = self._post(
                            self._session, self._params, text, source, target
                        )
                        break
                    except Exception:
                        # token/IG may have expired - refresh once and retry
                        if attempt == 0:
                            try:
                                self._session, self._params = self._bootstrap()
                            except Exception:
                                break
                if translated is None:
                    raise TranslationError("Bing request failed")
                out.append(translated)
            return out


# ---------------------------------------------------------------------------
# Free engine: Google Translate (undocumented gtx endpoint, no API key)
# ---------------------------------------------------------------------------
class GoogleTranslator:
    id = "google"
    label = "Google"
    URL = "https://translate.googleapis.com/translate_a/single"

    def _one(self, text, source, target):
        resp = requests.get(
            self.URL,
            params={
                "client": "gtx",
                "sl": _lang(source, "google"),
                "tl": _lang(target, "google"),
                "dt": "t",
                "q": text,
            },
            headers=_UA,
            timeout=TIMEOUT_FREE,
        )
        resp.raise_for_status()
        segments = resp.json()[0]
        return "".join(seg[0] for seg in segments if seg and seg[0])

    def translate(self, texts, source, target, cfg=None):
        return [self._one(text, source, target) for text in texts]


# ---------------------------------------------------------------------------
# Free engine: MyMemory (keyless, strict daily quota -> last resort only)
# ---------------------------------------------------------------------------
class MyMemoryTranslator:
    id = "mymemory"
    label = "MyMemory"
    URL = "https://api.mymemory.translated.net/get"

    def translate(self, texts, source, target, cfg=None):
        out = []
        for index, text in enumerate(texts):
            if index:
                time.sleep(0.2)  # be gentle with the anonymous quota
            resp = requests.get(
                self.URL,
                params={
                    "q": text,
                    "langpair": "%s|%s"
                    % (_lang(source, "mymemory"), _lang(target, "mymemory")),
                },
                headers=_UA,
                timeout=TIMEOUT_FREE,
            )
            resp.raise_for_status()
            data = resp.json()
            translated = (data.get("responseData") or {}).get("translatedText")
            if not translated:
                raise TranslationError(data.get("responseDetails") or "MyMemory error")
            out.append(translated)
        return out


# ---------------------------------------------------------------------------
# User supplied AI endpoint (OpenAI-compatible /chat/completions)
# ---------------------------------------------------------------------------
class AITranslator:
    id = "ai"
    label = "AI API"

    @staticmethod
    def endpoint(cfg):
        base = (cfg.get("ai_base_url") or "").strip().rstrip("/")
        if not base:
            base = "https://api.openai.com/v1"
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    @staticmethod
    def _parse(raw, count):
        """Accept a JSON array first, then a plain one-translation-per-line reply."""
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I).strip()
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                if (
                    isinstance(parsed, list)
                    and len(parsed) == count
                    and all(isinstance(x, str) for x in parsed)
                ):
                    return [x.strip() for x in parsed]
            except (ValueError, TypeError):
                pass
        lines = []
        for line in cleaned.splitlines():
            line = re.sub(r"^\s*\d+\s*[|.)\-:]\s*", "", line.strip())
            line = line.strip().strip('"')
            if line and not line.startswith("```"):
                lines.append(line)
        if len(lines) == count:
            return lines
        return None

    def translate(self, texts, source, target, cfg):
        api_key = (cfg.get("ai_api_key") or "").strip()
        if not api_key:
            raise TranslationError("API key is required for the AI engine")
        model = (cfg.get("ai_model") or "").strip() or "gpt-4o-mini"
        src_desc = _ai_lang(source)
        tgt_desc = _ai_lang(target)
        system = (
            "You are a professional song-lyric translator. Translate naturally, "
            "concisely and poetically while preserving meaning. Reply with ONLY "
            "a JSON array of strings. No markdown, no commentary, no numbering."
        )
        user = (
            "Translate these %d lyric lines from %s to %s.\n"
            "Return a JSON array of exactly %d strings, one translation per input "
            "line, in the same order. Keep the line count exact. Do not merge, "
            "split or omit lines. Keep short lines short.\n\n"
            "INPUT (JSON array):\n%s"
            % (
                len(texts),
                src_desc,
                tgt_desc,
                len(texts),
                json.dumps(texts, ensure_ascii=False),
            )
        )
        headers = {
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        }
        headers.update(_UA)
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        endpoint = self.endpoint(cfg)
        session = requests.Session()
        # A machine-wide proxy must not swallow localhost endpoints such as
        # Ollama or LM Studio, while remote providers keep normal proxy support.
        if re.search(
            r"://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::|\/)",
            endpoint,
            re.I,
        ):
            session.trust_env = False
        resp = session.post(
            endpoint, headers=headers, json=body, timeout=TIMEOUT_AI
        )
        if resp.status_code == 401 or resp.status_code == 403:
            raise TranslationError("AI API rejected the key (HTTP %d)" % resp.status_code)
        resp.raise_for_status()
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise TranslationError("Unexpected AI API response: %s" % exc)
        if isinstance(content, list):  # some gateways return content parts
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        parsed = self._parse(str(content), len(texts))
        if parsed is None:
            raise TranslationError(
                "AI reply did not contain exactly %d lines; refusing to misalign lyrics"
                % len(texts)
            )
        return parsed


_ENGINE_CLASSES = {
    "bing": BingTranslator,
    "google": GoogleTranslator,
    "mymemory": MyMemoryTranslator,
    "ai": AITranslator,
}


_BING_SINGLETON = None
_BING_LOCK = threading.Lock()


def build_engine_chain(engine_id, cfg):
    """Return engine instances in the order they should be attempted.

    Bing keeps a live session/token, so reuse one instance across songs.
    """
    global _BING_SINGLETON
    order = {
        "auto": ["bing", "google", "mymemory"],
        "bing": ["bing"],
        "google": ["google"],
        "mymemory": ["mymemory"],
        "ai": ["ai"],
    }.get(engine_id, ["bing", "google", "mymemory"])
    chain = []
    for name in order:
        if name == "bing":
            with _BING_LOCK:
                if _BING_SINGLETON is None:
                    _BING_SINGLETON = BingTranslator()
                chain.append(_BING_SINGLETON)
        else:
            chain.append(_ENGINE_CLASSES[name]())
    return chain


def _batch(engine, lines, source, target, cfg):
    """Translate a list of lines; free engines use newline-joined batches."""
    if engine.id == "ai":
        return engine.translate(lines, source, target, cfg)
    if engine.id == "mymemory":
        return engine.translate(lines, source, target, cfg)

    # Bing / Google preserve a newline-joined block, so one request handles many lines.
    joined = "\n".join(lines)
    raw = engine.translate([joined], source, target, cfg)[0]
    parts = raw.split("\n")
    if len(parts) == len(lines) and all(p.strip() for p in parts):
        return [p.strip() for p in parts]
    # Line count drifted -> translate line by line so nothing is misaligned.
    return [p.strip() for p in engine.translate(lines, source, target, cfg)]


def translate_lines(
    texts,
    cfg,
    cache,
    cache_lock=None,
    on_progress=None,
    is_cancelled=None,
):
    """Translate ``texts`` and return ``{index: translated_text}``.

    ``cache`` maps ``(config_signature, source_text)`` -> translation and is
    shared across songs. ``on_progress`` is called with the accumulated mapping
    after every successful chunk, so the UI can reveal translations gradually.
    """
    cache_lock = cache_lock or threading.Lock()
    signature = config_signature(cfg)
    source = cfg.get("translation_source", "auto")
    target = cfg.get("translation_target", "zh-Hans")
    result = {}
    todo = []
    for index, text in enumerate(texts):
        if not is_translatable(text):
            continue
        key = (signature, text)
        with cache_lock:
            cached = cache.get(key)
        if cached is not None:
            result[index] = cached
        else:
            todo.append(index)

    if on_progress and result:
        on_progress(dict(result))
    if not todo:
        return result

    chain = build_engine_chain(cfg.get("translation_engine", "auto"), cfg)
    mymemory_used = 0

    for start in range(0, len(todo), CHUNK_SIZE):
        if is_cancelled and is_cancelled():
            return result
        indices = todo[start : start + CHUNK_SIZE]
        lines = [texts[i] for i in indices]
        translated = None
        used_engine = None
        chunk_errors = []
        for engine in chain:
            if engine.id == "mymemory" and mymemory_used >= MYMEMORY_BUDGET:
                continue
            try:
                translated = _batch(engine, lines, source, target, cfg)
                if len(translated) != len(lines):
                    raise TranslationError("mismatched line count")
                used_engine = engine.id
                break
            except Exception as exc:
                chunk_errors.append("%s: %s" % (engine.label, exc))
                translated = None
        if translated is None:
            raise TranslationError(
                "; ".join(chunk_errors) if chunk_errors else "No engine available"
            )
        if used_engine == "mymemory":
            mymemory_used += len(lines)
        for index, text, value in zip(indices, lines, translated):
            value = (value or "").strip()
            if not value:
                continue
            result[index] = value
            with cache_lock:
                cache[(signature, text)] = value
                if len(cache) > 3000:
                    for stale in list(cache.keys())[:500]:
                        cache.pop(stale, None)
        if on_progress:
            on_progress(dict(result))
    return result


def test_connection(cfg):
    """Return ``(ok, message)`` for the Test Connection button."""
    phrase = "Hello, world! The sun is shining."
    try:
        result = translate_lines([phrase], cfg, {}, threading.Lock())
        translated = result.get(0, "")
        if not translated:
            return False, "Empty translation returned"
        return True, "%s -> %s" % (phrase, translated)
    except Exception as exc:
        return False, str(exc)
