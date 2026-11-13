"""Multi-source synced-lyrics lookup for MusicLine.

Why this module exists
----------------------
The original app passed ``"<title> <artist>"`` straight to
``syncedlyrics.search()``.  That is fragile for three reasons:

* Apple Music (and several other players) put extra text into the artist
  field, e.g. ``"Taylor Swift — Red"`` or ``"DECO*27 — Ghost"``, and may
  change that text when the window is minimised.  The raw string was used as
  the track identity, so a metadata flicker looked like a track change and
  wiped the lyrics that were already on screen.
* ``syncedlyrics`` tries Musixmatch first (unreachable on many networks,
  costing ~2s every time) and its Lrclib provider only inspects the *first*
  ranked result, regardless of whether that result has synced lyrics.
* There was no caching, so every flicker meant another network round trip.

This module normalises metadata into a stable key, caches LRC both in memory
and on disk, and queries several independent providers in order.  Only LRC
containing real timestamps is accepted.

Public API
----------
    normalize_key(title, artist) -> str        stable track identity
    clean_title / clean_artist   -> str        cleaned metadata
    get_lrc(title, artist, source="auto") -> Result
    clear_cache() -> int
    cache_stats() -> (memory_count, disk_count)

No Qt dependency: everything here is safe to call from a worker thread.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

import requests

TIMEOUT = (3, 8)
NEGATIVE_TTL = 30.0
MAX_LOG_BYTES = 256 * 1024

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

# NetEase rejects the search endpoint without a cookie.  A generic one is
# enough; the token values do not need to belong to a real account.
NETEASE_COOKIE = (
    "appver=2.0.2; os=pc; NMTID=MjAyNktB; _ntes_nnid=kblyrics,1700000000000; "
    "_ntes_nuid=kblyrics; WNMCID=kblyrics.1700000000000.01.0; WEVNSM=1.0.0; "
    "playerid=94262567"
)

_LOCK = threading.Lock()
_MEM: dict[str, str] = {}
_NEG: dict[str, float] = {}


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()
CACHE_DIR = os.path.join(BASE_DIR, "lyrics_cache")
LOG_PATH = os.path.join(BASE_DIR, "lyrics.log")


def log(message: str) -> None:
    """Append one diagnostic line; kept small and never fatal."""
    try:
        line = "%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message)
        with _LOCK:
            if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > MAX_LOG_BYTES:
                with open(LOG_PATH, "w", encoding="utf-8"):
                    pass
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(line)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Metadata normalisation
# --------------------------------------------------------------------------

_BRACKET = re.compile(r"\s*[\(\[]([^)\]]{1,70})[)\]]")
_NOISE_WORDS = (
    "explicit", "remaster", "version", "deluxe", "official", "video",
    "audio", "remix", "instrumental", "karaoke", "single", "radio edit",
    "acoustic", "mono", "stereo", "anniversary", "demo", "re-record",
    "feat", "ft.", "live at", "live from", "edit", "mix", "ep",
)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_SEPARATOR = re.compile(r"\s+[—–]\s+|\s+-\s+")
_FEAT = re.compile(r"\s+(?:feat\.?|ft\.?|featuring)\s+.*$", re.IGNORECASE)
_TAIL_SUFFIX = re.compile(r"\s+[-—–]\s+(?:single|ep|album)\s*$", re.IGNORECASE)
_WS = re.compile(r"\s+")


def _strip_bracket_noise(text: str) -> str:
    def replace(match: re.Match) -> str:
        inner = match.group(1)
        low = inner.lower()
        if any(word in low for word in _NOISE_WORDS) or _YEAR.search(inner):
            return " "
        return match.group(0)

    return _BRACKET.sub(replace, text)


def clean_title(title: str) -> str:
    """Remove version/edition suffixes while keeping the real song name."""
    text = unicodedata.normalize("NFKC", title or "")
    text = _strip_bracket_noise(text)
    text = _TAIL_SUFFIX.sub("", text)
    text = _FEAT.sub("", text)
    text = _WS.sub(" ", text).strip(" -—–_")
    return text.strip()


def clean_artist(artist: str) -> str:
    """Apple Music stores ``Artist — Album``; keep only the artist."""
    text = unicodedata.normalize("NFKC", artist or "")
    text = _SEPARATOR.split(text)[0]
    text = _strip_bracket_noise(text)
    text = _FEAT.sub("", text)
    text = _WS.sub(" ", text).strip(" -—–_")
    return text.strip()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in text if ch.isalnum())


def normalize_key(title: str, artist: str) -> str:
    """Stable identity used both for track de-bouncing and for the cache."""
    return "%s|%s" % (_fold(clean_title(title)), _fold(clean_artist(artist)))


def _similarity(a: str, b: str) -> float:
    left, right = _fold(a), _fold(b)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _query_variants(title: str, artist: str):
    """Yield (title, artist) pairs from cleanest to rawest, deduplicated."""
    raw_t = unicodedata.normalize("NFKC", title or "").strip()
    raw_a = unicodedata.normalize("NFKC", artist or "").strip()
    clean_t, clean_a = clean_title(title), clean_artist(artist)
    pairs = [
        (clean_t, clean_a),
        (raw_t, clean_a),
        (clean_t, raw_a),
        (raw_t, raw_a),
    ]
    seen = set()
    for t, a in pairs:
        if not t:
            continue
        sig = (_fold(t), _fold(a))
        if sig in seen:
            continue
        seen.add(sig)
        yield t, a


# --------------------------------------------------------------------------
# LRC validation & cache
# --------------------------------------------------------------------------

_TIMESTAMP = re.compile(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]")


def valid_lrc(text: Optional[str]) -> bool:
    """Only accept lyrics that can actually be synced line by line."""
    if not text or len(text) < 20:
        return False
    return len(_TIMESTAMP.findall(text)) >= 2


def _cache_path(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:24]
    return os.path.join(CACHE_DIR, digest + ".json")


def _disk_read(key: str) -> Optional[str]:
    try:
        with open(_cache_path(key), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        value = data.get("lrc")
        return value if valid_lrc(value) else None
    except Exception:
        return None


def _store(key: str, lrc: str, source: str, title: str, artist: str) -> None:
    with _LOCK:
        _MEM[key] = lrc
        _NEG.pop(key, None)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = _cache_path(key)
        tmp = path + ".tmp"
        payload = {
            "title": title,
            "artist": artist,
            "source": source,
            "saved_at": time.time(),
            "lrc": lrc,
        }
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as exc:
        log("cache write failed: %s" % exc)


def clear_cache() -> int:
    """Drop memory + disk cache. Returns the number of files removed."""
    with _LOCK:
        _MEM.clear()
        _NEG.clear()
    removed = 0
    try:
        if os.path.isdir(CACHE_DIR):
            for name in os.listdir(CACHE_DIR):
                if name.endswith(".json"):
                    os.remove(os.path.join(CACHE_DIR, name))
                    removed += 1
    except Exception as exc:
        log("cache clear failed: %s" % exc)
    log("cache cleared (%d files)" % removed)
    return removed


def cache_stats():
    with _LOCK:
        mem = len(_MEM)
    try:
        disk = sum(1 for n in os.listdir(CACHE_DIR) if n.endswith(".json")) if os.path.isdir(CACHE_DIR) else 0
    except Exception:
        disk = 0
    return mem, disk


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------

def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(UA)
    return session


def _lrclib_exact(title: str, artist: str, session: requests.Session):
    """LRCLIB /api/get: exact match, separate fields, returns syncedLyrics."""
    for t, a in _query_variants(title, artist):
        if not a:
            continue
        response = session.get(
            "https://lrclib.net/api/get",
            params={"track_name": t, "artist_name": a},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            lrc = (response.json() or {}).get("syncedLyrics") or ""
            if valid_lrc(lrc):
                return lrc, "%s / %s" % (t, a)
    return None, "no exact match"


def _lrclib_search(title: str, artist: str, session: requests.Session):
    """LRCLIB /api/search: rank candidates and take the first WITH timestamps."""
    query = "%s %s" % (clean_title(title), clean_artist(artist))
    response = session.get(
        "https://lrclib.net/api/search", params={"q": query.strip()}, timeout=TIMEOUT
    )
    if response.status_code != 200:
        return None, "HTTP %s" % response.status_code
    tracks = response.json() or []
    if not isinstance(tracks, list):
        return None, "unexpected response"

    def rank(item):
        return max(
            _similarity(title, item.get("trackName", "")),
            _similarity(artist, item.get("artistName", "")),
        )

    ranked = sorted(tracks, key=lambda item: -rank(item))
    for item in ranked[:15]:
        lrc = item.get("syncedLyrics") or ""
        if not valid_lrc(lrc):
            continue
        if rank(item) < 0.42:
            continue
        return lrc, item.get("trackName", "")[:50]
    return None, "%d results, none with synced lyrics" % len(tracks)


def _qqmusic(title: str, artist: str, session: requests.Session):
    """QQ Music: search for songmid, then fetch plain (non-base64) LRC."""
    headers = {"Referer": "https://y.qq.com/"}
    query = "%s %s" % (clean_title(title), clean_artist(artist))
    response = session.get(
        "https://c.y.qq.com/soso/fcgi-bin/client_search_cp",
        params={"w": query.strip(), "format": "json", "n": 8, "p": 1},
        headers=headers,
        timeout=TIMEOUT,
    )
    songs = ((response.json() or {}).get("data") or {}).get("song") or {}
    candidates = songs.get("list") or []
    for song in candidates[:6]:
        name = song.get("songname", "") or ""
        if _similarity(title, name) < 0.45:
            continue
        mid = song.get("songmid")
        if not mid:
            continue
        detail = session.get(
            "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg",
            params={"songmid": mid, "format": "json", "nobase64": 1},
            headers=headers,
            timeout=TIMEOUT,
        )
        payload = detail.json() or {}
        if payload.get("retcode") not in (0, None):
            continue
        lrc = payload.get("lyric") or ""
        if not valid_lrc(lrc):
            import base64

            try:
                lrc = base64.b64decode(lrc).decode("utf-8", "replace")
            except Exception:
                lrc = ""
        if valid_lrc(lrc):
            return lrc, name[:50]
    return None, "%d candidates" % len(candidates)


def _netease(title: str, artist: str, session: requests.Session):
    """NetEase Cloud Music: search for a song id, then fetch its LRC."""
    headers = {"Referer": "https://music.163.com/", "Cookie": NETEASE_COOKIE}
    query = "%s %s" % (clean_title(title), clean_artist(artist))
    response = session.get(
        "https://music.163.com/api/search/pc",
        params={"s": query.strip(), "type": 1, "limit": 8, "offset": 0},
        headers=headers,
        timeout=TIMEOUT,
    )
    payload = response.json() or {}
    songs = (payload.get("result") or {}).get("songs") or []
    for song in songs[:6]:
        name = song.get("name", "") or ""
        if _similarity(title, name) < 0.45:
            continue
        song_id = song.get("id")
        if not song_id:
            continue
        detail = session.get(
            "https://music.163.com/api/song/lyric",
            params={"id": song_id, "lv": 1, "kv": 1, "tv": -1},
            headers=headers,
            timeout=TIMEOUT,
        )
        lrc = ((detail.json() or {}).get("lrc") or {}).get("lyric") or ""
        if valid_lrc(lrc):
            return lrc, name[:50]
    return None, "code %s, %d candidates" % (payload.get("code"), len(songs))


PROVIDERS = {
    "lrclib_exact": _lrclib_exact,
    "lrclib_search": _lrclib_search,
    "qqmusic": _qqmusic,
    "netease": _netease,
}

CHAINS = {
    "auto": ["lrclib_exact", "qqmusic", "lrclib_search", "netease"],
    "lrclib": ["lrclib_exact", "lrclib_search"],
    "qqmusic": ["qqmusic"],
    "netease": ["netease"],
}

SOURCE_LABELS = {
    "auto": "Auto (LRCLIB > QQ Music > NetEase)",
    "lrclib": "LRCLIB only",
    "qqmusic": "QQ Music only",
    "netease": "NetEase Cloud Music only",
}


@dataclass
class Result:
    lrc: Optional[str]
    source: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.lrc)


def get_lrc(title: str, artist: str, source: str = "auto") -> Result:
    """Fetch synced lyrics. Never raises; safe to call from a worker thread."""
    key = normalize_key(title, artist)
    started = time.time()

    with _LOCK:
        cached = _MEM.get(key)
        failed_recently = time.time() - _NEG.get(key, 0.0) < NEGATIVE_TTL
    if cached:
        log("[cache-mem] %s|%s" % (title, artist))
        return Result(cached, "cache")
    if failed_recently:
        return Result(None, "recent-failure", "suppressed repeated lookup")

    disk = _disk_read(key)
    if disk:
        with _LOCK:
            _MEM[key] = disk
        log("[cache-disk] %s|%s" % (title, artist))
        return Result(disk, "cache")

    chain = CHAINS.get(source) or CHAINS["auto"]
    session = _session()
    notes = []
    for name in chain:
        provider = PROVIDERS.get(name)
        if provider is None:
            continue
        t0 = time.time()
        try:
            lrc, detail = provider(title, artist, session)
        except Exception as exc:
            lrc, detail = None, "%s: %s" % (type(exc).__name__, str(exc)[:80])
        notes.append("%s=%.2fs(%s)" % (name, time.time() - t0, "hit" if lrc else detail))
        if lrc and valid_lrc(lrc):
            _store(key, lrc, name, title, artist)
            log("[OK] %s|%s -> %s (%.2fs) %s" % (
                title, artist, name, time.time() - started, " ".join(notes)))
            return Result(lrc, name, detail)

    with _LOCK:
        _NEG[key] = time.time()
    log("[FAIL] %s|%s (%.2fs) %s" % (
        title, artist, time.time() - started, " ".join(notes)))
    return Result(None, "none", " ".join(notes))
