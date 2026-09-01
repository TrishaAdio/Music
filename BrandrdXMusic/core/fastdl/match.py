"""
Title normalisation and candidate scoring.

When a request is served from a music catalogue rather than the exact YouTube
video, correctness stops being free: a naive "first search hit" happily returns
a karaoke cover or a sped-up remix. Measured examples that motivated this file:
"Luis Fonsi - Despacito" matched "Despacito (Bestacito remix)", and
"OneRepublic - Counting Stars" matched an "Originally Perfomed by..." cover.

So every candidate is scored, and the engine refuses anything under a
confidence floor, falling through to the next provider instead.
"""

import difflib
import html
import re
from typing import Any, Dict, List, Optional, Tuple

# Promo junk that appears in YouTube titles but never in catalogue titles.
_NOISE = re.compile(
    r"\b("
    r"official\s*(music\s*)?video|official\s*audio|official\s*lyric[s]?\s*video|"
    r"lyric[s]?\s*video|with\s*lyrics|lyrics|full\s*video\s*song|full\s*video|"
    r"video\s*song|full\s*song|full\s*audio|audio\s*song|full\s*movie|"
    r"hd\s*video|4k|1080p|720p|hq|hd|remastered|reupload|"
    r"out\s*now|new\s*song|latest\s*song|"
    r"official|exclusive|teaser|trailer|promo|announcement"
    r")\b",
    re.I,
)

# Markers that mean "this is not the recording that was asked for".
_DERIVATIVE = re.compile(
    r"\b("
    r"karaoke|instrumental|backing\s*track|"
    r"originally\s*perfor?m(ed|d)?|as\s*made\s*famous\s*by|in\s*the\s*style\s*of|"
    r"tribute|made\s*popular\s*by|cover\s*version|\bcover\b|"
    r"8d\s*audio|slowed|reverb|nightcore|lofi|lo-fi|"
    # "sped up", "spedup", "speed up", "speedup", "SpeedUp Version"
    r"spe?e?d\s*up|speedup|spedup|fast\s*version|slow\s*version|"
    r"mashup|medley|ringtone|instrumental|"
    # "12minutes ver", "1 hour", "extended", "loop" - long edits, not the track
    r"\d+\s*(?:minutes?|mins?|hours?|hrs?)|extended\s*(?:version|mix)?|"
    r"\bloop(ed)?\b|"
    r"cont(inuous)?\s*mix"
    r")\b",
    re.I,
)

# Remix-ish markers: penalised, but only when the request did not ask for one.
_REMIX = re.compile(r"\b(remix|rmx|mix|dj\s+\w+|flip|bootleg|edit|refix|mashup)\b", re.I)

_FEATURE = re.compile(r"\b(feat\.?|ft\.?|featuring|with)\b", re.I)


def strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()


def normalise(text: Optional[str]) -> str:
    """Collapse to comparable alphanumerics."""
    return re.sub(r"[^a-z0-9]+", "", strip_html(text).lower())


def clean_query(title: Optional[str]) -> str:
    """
    Turn a YouTube-style title into a catalogue-style search query.

    "Kesariya - Brahmastra | Ranbir Kapoor, Alia Bhatt | Pritam" -> "Kesariya Brahmastra"
    """
    text = strip_html(title)
    if not text:
        return ""
    text = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text)  # bracketed extras
    text = _NOISE.sub(" ", text)
    text = re.sub(r"\|.*$", " ", text)  # Indian-music titles pile credits after |
    text = re.sub(r"\s*[-–—]\s*", " ", text)
    text = _FEATURE.sub(" ", text)
    text = re.sub(r"[^\w\s&']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _token_set(text: str) -> set:
    return {t for t in re.split(r"\s+", strip_html(text).lower()) if len(t) > 1}


def wants_derivative(query: Optional[str]) -> bool:
    """Did the user explicitly ask for a remix/lofi/slowed version?"""
    q = strip_html(query)
    return bool(_REMIX.search(q) or _DERIVATIVE.search(q))


def score_candidate(
    candidate_title: str,
    query: str,
    *,
    candidate_artists: str = "",
    expected_artist: str = "",
    candidate_duration: Optional[int] = None,
    expected_duration: Optional[int] = None,
    allow_derivative: bool = False,
) -> float:
    """
    Confidence that `candidate_title` is the recording described by `query`.

    Roughly 0-140. Duration agreement is the strongest positive signal because
    it separates the real track from covers and edits far better than text does.
    """
    cand_norm = normalise(candidate_title)
    query_norm = normalise(query)
    if not cand_norm or not query_norm:
        return 0.0

    # Two complementary coverage signals, because YouTube titles bundle the
    # artist and extra context into one string ("Luis Fonsi - Despacito ft.
    # Daddy Yankee", "Kesariya - Brahmastra | Ranbir Kapoor") while catalogues
    # store a bare title plus separate artist fields. Raw string similarity
    # alone scores the correct track terribly in both directions.
    query_tokens = _token_set(query)
    title_tokens = _token_set(candidate_title)
    candidate_tokens = _token_set(f"{candidate_title} {candidate_artists}")

    score = 0.0

    # (a) How much of the request does the candidate explain? Checked against
    #     title AND artist, so "Luis Fonsi" in the query matches the artist field.
    if query_tokens and candidate_tokens:
        score += (len(query_tokens & candidate_tokens) / len(query_tokens)) * 40.0

    # (b) How much of the candidate's own title is accounted for by the request?
    #     This is what identifies "Kesariya" as the right answer for
    #     "Kesariya Brahmastra": the whole title appears in the query. It also
    #     punishes padded titles like "Believer (Originally Perfomed By ...)".
    if title_tokens and query_tokens:
        score += (len(title_tokens & query_tokens) / len(title_tokens)) * 30.0

    # Character-level similarity, as a secondary signal.
    score += difflib.SequenceMatcher(None, cand_norm, query_norm).ratio() * 20.0

    # Containment: "Kesariya" inside "Kesariya Brahmastra" should rank well.
    if cand_norm in query_norm or query_norm in cand_norm:
        score += 15.0

    # Explicit artist agreement. YouTube channel names often carry a VEVO suffix.
    if expected_artist and candidate_artists:
        want = normalise(expected_artist).replace("vevo", "").replace("official", "")
        have = normalise(candidate_artists)
        if want and have and (want in have or have in want):
            score += 15.0
        elif want and have:
            score += difflib.SequenceMatcher(None, want, have).ratio() * 8.0

    # Duration agreement.
    #
    # Deliberately a strong bonus but only a mild penalty in the middle band.
    # A YouTube music video is very often a different length from the album
    # track it corresponds to - the "Kesariya" video runs 2:53 while the release
    # is 4:28 - so an absolute-seconds veto rejects the *correct* song. Only
    # ratios that indicate a genuinely different item (a clipped preview, or a
    # looped/extended upload) are punished hard.
    if expected_duration and candidate_duration:
        candidate_seconds = int(candidate_duration)
        expected_seconds = int(expected_duration)
        delta = abs(candidate_seconds - expected_seconds)
        smaller = max(1, min(candidate_seconds, expected_seconds))
        ratio = max(candidate_seconds, expected_seconds) / smaller

        if delta <= 3:
            score += 30.0
        elif delta <= 10:
            score += 20.0
        elif delta <= 25:
            score += 8.0
        elif ratio <= 1.6:
            pass  # plausible video edit or alternate master
        elif ratio <= 2.2:
            score -= 18.0
        else:
            # Beyond ~2.2x the two are not the same item. Scale with the ratio
            # so a 12-minute upload of a 4-minute song cannot survive on the
            # strength of a perfect title and artist match alone.
            score -= min(80.0, 45.0 + (ratio - 2.2) * 25.0)

        # A short clip standing in for a full track is always wrong.
        if candidate_seconds < 60 and expected_seconds >= 120:
            score -= 50.0

    # Derivative penalties, skipped when the user asked for that flavour.
    if not allow_derivative:
        if _DERIVATIVE.search(strip_html(candidate_title)):
            score -= 55.0
        elif _REMIX.search(strip_html(candidate_title)) and not _REMIX.search(strip_html(query)):
            score -= 32.0

    return max(0.0, score)


def pick_best(
    candidates: List[Dict[str, Any]],
    query: str,
    *,
    expected_artist: str = "",
    expected_duration: Optional[int] = None,
    minimum: float = 0.0,
) -> Tuple[Optional[Dict[str, Any]], float]:
    """
    Score every candidate and return (best, score), or (None, best_score) when
    nothing clears `minimum`.

    Each candidate needs "title", and may carry "artists" and "duration".
    """
    allow_derivative = wants_derivative(query)
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for candidate in candidates:
        score = score_candidate(
            candidate.get("title") or "",
            query,
            candidate_artists=candidate.get("artists") or "",
            expected_artist=expected_artist,
            candidate_duration=candidate.get("duration"),
            expected_duration=expected_duration,
            allow_derivative=allow_derivative,
        )
        if score > best_score:
            best, best_score = candidate, score

    if best is not None and best_score >= minimum:
        return best, best_score
    return None, best_score
