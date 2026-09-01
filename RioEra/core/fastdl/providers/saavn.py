"""
JioSaavn provider - the primary fast path.

Why this is the default:
  * no cookies, no API key, no PO token, no login, nothing that expires
  * search responds in ~0.3s and the media host is a plain public CDN
  * audio is 320kbps AAC in an MP4 container, which ffmpeg streams natively

The one non-obvious step is the media URL. The search response carries
`encrypted_media_url`, a base64 DES-ECB blob. Decrypting it yields an *unsigned*
CDN URL that needs no auth at all. The alternative documented route
(`song.generateAuthToken`) hands back a signed link that is bound to the
caller/IP and answers 403 from a server, so it is deliberately not used here.
"""

import base64
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from .. import match
from ..config import fastdl_config
from ..models import NotFound, ProviderError, Resolved, TrackRequest
from ..net import get_json, probe

NAME = "saavn"

_API = "https://www.jiosaavn.com/api.php"
_COMMON = {
    "_format": "json",
    "_marker": "0",
    "api_version": "4",
    "ctx": "web6dot0",
}
# Static DES key used by the JioSaavn web player for media URL obfuscation.
_DES_KEY = b"38346591"


def _decrypt_media_url(encrypted: str) -> Optional[str]:
    """DES-ECB decrypt + strip PKCS#5 padding."""
    try:
        from Crypto.Cipher import DES  # pycryptodome
    except ImportError:  # pragma: no cover - dependency is declared
        try:
            from Cryptodome.Cipher import DES  # type: ignore
        except ImportError:
            raise ProviderError(
                "pycryptodome is required for the saavn provider "
                "(pip install pycryptodome)"
            )
    try:
        raw = base64.b64decode(encrypted)
        decrypted = DES.new(_DES_KEY, DES.MODE_ECB).decrypt(raw)
        pad = decrypted[-1]
        if 1 <= pad <= 8:
            decrypted = decrypted[:-pad]
        url = decrypted.decode("utf-8", "replace").strip()
        return url or None
    except Exception:
        return None


_BITRATE_SUFFIXES = ("_320.mp4", "_160.mp4", "_96.mp4", "_48.mp4", "_12.mp4")


def _url_variants(base_url: str) -> List[Tuple[str, str]]:
    """
    Build the quality ladder as (url, bitrate_label) pairs.

    Decrypted URLs end in `_96.mp4`; swapping that number selects the bitrate.
    Some catalogue items only exist at lower bitrates, so each rung is probed
    in order and the first reachable one wins.
    """
    stem: Optional[str] = None
    for suffix in _BITRATE_SUFFIXES:
        if base_url.endswith(suffix):
            stem = base_url[: -len(suffix)]
            break

    variants: List[Tuple[str, str]] = []
    if stem is not None:
        for bitrate in fastdl_config.saavn_bitrates:
            candidate = f"{stem}_{bitrate}.mp4"
            if candidate not in [url for url, _ in variants]:
                variants.append((candidate, bitrate))

    # Always keep the untouched URL as a final rung in case the naming
    # convention changes upstream.
    if base_url not in [url for url, _ in variants]:
        variants.append((base_url, "source"))
    return variants


def _artists_of(more_info: Dict[str, Any]) -> str:
    artist_map = more_info.get("artistMap") or {}
    names: List[str] = []
    for bucket in ("primary_artists", "featured_artists", "artists"):
        for entry in artist_map.get(bucket) or []:
            name = (entry or {}).get("name")
            if name and name not in names:
                names.append(name)
    if not names:
        for key in ("primary_artists", "singers", "music"):
            value = more_info.get(key)
            if value:
                names.append(str(value))
                break
    return ", ".join(names)


async def _search(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    params = dict(_COMMON)
    params.update({"__call": "search.getResults", "q": query, "n": str(limit), "p": "1"})
    url = f"{_API}?{urllib.parse.urlencode(params)}"
    data = await get_json(url, timeout=fastdl_config.resolve_timeout, retries=1)
    if isinstance(data, dict):
        return data.get("results") or []
    return []


def _to_candidate(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    more_info = item.get("more_info") or {}
    encrypted = more_info.get("encrypted_media_url")
    if not encrypted:
        return None
    try:
        duration = int(more_info.get("duration") or 0) or None
    except (TypeError, ValueError):
        duration = None
    image = (item.get("image") or "").replace("150x150", "500x500")
    return {
        "title": match.strip_html(item.get("title")),
        "artists": match.strip_html(_artists_of(more_info)),
        "duration": duration,
        "encrypted": encrypted,
        "thumbnail": image or None,
    }


async def resolve(request: TrackRequest) -> Resolved:
    if request.want_video:
        # Audio catalogue only; the engine will fall through for video.
        raise NotFound("saavn is audio-only")

    query = (request.query or request.expected_title or "").strip()
    if not query:
        raise NotFound("saavn needs a text query")

    cleaned = match.clean_query(query) or query
    results = await _search(cleaned)
    if not results and cleaned != query:
        results = await _search(query)
    if not results:
        raise NotFound(f"no saavn results for {cleaned!r}")

    candidates = [c for c in (_to_candidate(item) for item in results) if c]
    if not candidates:
        raise NotFound("saavn results carried no playable media")

    best, score = match.pick_best(
        candidates,
        cleaned,
        expected_artist=request.expected_artist or "",
        expected_duration=request.expected_duration,
        minimum=fastdl_config.min_match_score,
    )
    if best is None:
        raise NotFound(
            f"best saavn match scored {score:.0f} < {fastdl_config.min_match_score:.0f} "
            f"for {cleaned!r}"
        )

    decrypted = _decrypt_media_url(best["encrypted"])
    if not decrypted:
        raise ProviderError("could not decrypt saavn media url")

    last_status = "unknown"
    for candidate_url, bitrate in _url_variants(decrypted):
        ok, size, ranges = await probe(candidate_url)
        if ok:
            return Resolved(
                url=candidate_url,
                provider=NAME,
                ext="m4a",
                size=size,
                supports_ranges=ranges,
                title=best.get("title"),
                artists=best.get("artists"),
                duration=best.get("duration"),
                thumbnail=best.get("thumbnail"),
                bitrate=bitrate,
                score=score,
            )
        last_status = f"probe failed for {bitrate}"

    raise ProviderError(f"saavn media url not reachable ({last_status})")
