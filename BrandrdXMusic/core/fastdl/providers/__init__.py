"""Provider registry.

Each provider exposes `NAME` and `async def resolve(TrackRequest) -> Resolved`,
raising NotFound/ProviderError to hand control to the next provider.
"""

from . import custom, innertube, saavn, soundcloud, ytdlp

REGISTRY = {
    saavn.NAME: saavn,
    soundcloud.NAME: soundcloud,
    innertube.NAME: innertube,
    custom.NAME: custom,
    ytdlp.NAME: ytdlp,
}

__all__ = ["REGISTRY", "saavn", "soundcloud", "innertube", "custom", "ytdlp"]
