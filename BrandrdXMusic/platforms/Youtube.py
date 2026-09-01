import asyncio
import os
import re
from typing import Union, Optional, List
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from BrandrdXMusic.utils.formatters import time_to_seconds
import aiohttp
from BrandrdXMusic import LOGGER

YOUR_API_URL = None
FALLBACK_API_URL = "https://shrutibots.site"

# Security patterns to detect malicious commands
MALICIOUS_PATTERNS = [
    r'\$\{IFS\}',           # IFS variable injection
    r'curl\s+',             # curl command
    r'wget\s+',             # wget command
    r'\|\s*\w+',            # pipe to commands
    r';\s*\w+',             # command chaining
    r'&&\s*\w+',            # command chaining
    r'\$\s*\(',             # command substitution
    r'`[^`]*`',             # backtick substitution
    r'cat\s+',              # cat command
    r'base64',              # base64 encoding
    r'tr\s+',               # tr command
    r'webhook\.site',       # webhook exfiltration
    r'pastebin\.com',       # pastebin exfiltration
]

async def is_malicious_link(link: str) -> tuple[bool, str]:
    """Check if a link contains malicious patterns"""
    if not link:
        return False, ""
    
    # Check for malicious patterns
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, link, re.IGNORECASE):
            return True, pattern
    
    # Check for command injection attempts
    dangerous_chars = [';', '&&', '||', '|', '`', '$', '(', ')', '{', '}', '<', '>']
    for char in dangerous_chars:
        if char in link:
            # Check if it's actually a YouTube URL
            if not any(domain in link.lower() for domain in ['youtube.com', 'youtu.be', 'youtube']):
                return True, f"suspicious character '{char}'"
    
    return False, ""

async def validate_youtube_url(link: str) -> bool:
    """Validate if the link is a proper YouTube URL"""
    youtube_patterns = [
        r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'^https?://(?:www\.)?youtu\.be/[\w-]+',
        r'^https?://(?:www\.)?youtube\.com/playlist\?list=[\w-]+',
        r'^https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, link, re.IGNORECASE):
            return True
    return False

async def load_api_url():
    global YOUR_API_URL
    logger = LOGGER("BrandrdXMusic.platforms.Youtube.py")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pastebin.com/raw/rLsBhAQa", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    YOUR_API_URL = content.strip()
                    logger.info("API URL loaded successfully")
                else:
                    YOUR_API_URL = FALLBACK_API_URL
                    logger.info("Using fallback API URL")
    except Exception:
        YOUR_API_URL = FALLBACK_API_URL
        logger.info("Using fallback API URL")

try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(load_api_url())
    else:
        loop.run_until_complete(load_api_url())
except RuntimeError:
    pass

async def download_song(link: str) -> Union[str, tuple[None, str]]:
    """Download song with security validation"""
    global YOUR_API_URL
    
    # Security check first
    is_malicious, pattern = await is_malicious_link(link)
    if is_malicious:
        return None, f"⚠️ **BLOCKED**: Malicious link detected!\nPattern: `{pattern}`\n\nYou can't play this nigah better stay on limit.\nMade by @siyourou"
    
    # Validate YouTube URL
    if not await validate_youtube_url(link):
        return None, "❌ Invalid YouTube URL. Please provide a valid YouTube link."
    
    if not YOUR_API_URL:
        await load_api_url()
        if not YOUR_API_URL:
            YOUR_API_URL = FALLBACK_API_URL
    
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link.split('/')[-1]

    if not video_id or len(video_id) < 3:
        return None, "❌ Invalid video ID"

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    if os.path.exists(file_path):
        return file_path, None

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "audio"}
            
            async with session.get(
                f"{YOUR_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    return None, "❌ Failed to connect to download service"

                data = await response.json()
                download_token = data.get("download_token")
                
                if not download_token:
                    return None, "❌ Failed to get download token"
                
                stream_url = f"{YOUR_API_URL}/stream/{video_id}?type=audio&token={download_token}"
                
                async with session.get(
                    stream_url,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as file_response:
                    if file_response.status == 302:
                        redirect_url = file_response.headers.get('Location')
                        if redirect_url:
                            async with session.get(redirect_url) as final_response:
                                if final_response.status != 200:
                                    return None, "❌ Download failed"
                                with open(file_path, "wb") as f:
                                    async for chunk in final_response.content.iter_chunked(16384):
                                        f.write(chunk)
                                return file_path, None
                    elif file_response.status == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in file_response.content.iter_chunked(16384):
                                f.write(chunk)
                        return file_path, None
                    else:
                        return None, "❌ Download failed"

    except Exception as e:
        return None, f"❌ Error: {str(e)}"

async def download_video(link: str) -> Union[str, tuple[None, str]]:
    """Download video with security validation"""
    global YOUR_API_URL
    
    # Security check first
    is_malicious, pattern = await is_malicious_link(link)
    if is_malicious:
        return None, f"⚠️ **BLOCKED**: Malicious link detected!\nPattern: `{pattern}`\n\nYou can't play this nigah better stay on limit.\nMade by @siyourou"
    
    # Validate YouTube URL
    if not await validate_youtube_url(link):
        return None, "❌ Invalid YouTube URL. Please provide a valid YouTube link."
    
    if not YOUR_API_URL:
        await load_api_url()
        if not YOUR_API_URL:
            YOUR_API_URL = FALLBACK_API_URL
    
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link.split('/')[-1]

    if not video_id or len(video_id) < 3:
        return None, "❌ Invalid video ID"

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    if os.path.exists(file_path):
        return file_path, None

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "video"}
            
            async with session.get(
                f"{YOUR_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    return None, "❌ Failed to connect to download service"

                data = await response.json()
                download_token = data.get("download_token")
                
                if not download_token:
                    return None, "❌ Failed to get download token"
                
                stream_url = f"{YOUR_API_URL}/stream/{video_id}?type=video&token={download_token}"
                
                async with session.get(
                    stream_url,
                    timeout=aiohttp.ClientTimeout(total=600)
                ) as file_response:
                    if file_response.status == 302:
                        redirect_url = file_response.headers.get('Location')
                        if redirect_url:
                            async with session.get(redirect_url) as final_response:
                                if final_response.status != 200:
                                    return None, "❌ Download failed"
                                with open(file_path, "wb") as f:
                                    async for chunk in final_response.content.iter_chunked(16384):
                                        f.write(chunk)
                                return file_path, None
                    elif file_response.status == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in file_response.content.iter_chunked(16384):
                                f.write(chunk)
                        return file_path, None
                    else:
                        return None, "❌ Download failed"

    except Exception as e:
        return None, f"❌ Error: {str(e)}"

async def get_playlist_videos(playlist_url: str, limit: int) -> List[str]:
    """Safely get playlist videos"""
    # Security check first
    is_malicious, pattern = await is_malicious_link(playlist_url)
    if is_malicious:
        return []
    
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': limit,
            'ignoreerrors': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            
            if 'entries' in playlist_info:
                video_ids = []
                for entry in playlist_info['entries']:
                    if entry and entry.get('id'):
                        video_ids.append(entry['id'])
                return video_ids
            return []
    except Exception as e:
        LOGGER("BrandrdXMusic.platforms.Youtube.py").error(f"Error getting playlist: {e}")
        return []

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            result = await download_video(link)
            if isinstance(result, tuple):
                success, error = result
                if success:
                    return 1, success
                else:
                    return 0, error
            elif result:
                return 1, result
            else:
                return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Check for malicious content
        is_malicious, pattern = await is_malicious_link(link)
        if is_malicious:
            return []
        
        return await get_playlist_videos(link, limit)

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Check for malicious content
        is_malicious, pattern = await is_malicious_link(link)
        if is_malicious:
            return None, None
        
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Check for malicious content
        is_malicious, pattern = await is_malicious_link(link)
        if is_malicious:
            return [], None
        
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Check for malicious content
        is_malicious, pattern = await is_malicious_link(link)
        if is_malicious:
            return None, None, None, None
        
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> tuple:
        if videoid:
            link = self.base + link

        try:
            if video:
                result = await download_video(link)
            else:
                result = await download_song(link)
            
            if isinstance(result, tuple):
                file_path, error = result
                if file_path:
                    return file_path, True
                else:
                    return error, False
            elif result:
                return result, True
            else:
                return "Download failed", False
        except Exception as e:
            return f"Error: {e}", False