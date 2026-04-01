"""
Anesis — AI Meditation Podcast Generator
Supabase storage integration and RSS 2.0 feed management.
"""
from __future__ import annotations

import logging
import os
import xml.dom.minidom
import xml.etree.ElementTree as ET
from email.utils import formatdate
from typing import Optional, Tuple

from config import PODCAST_CONFIG, SUPABASE_CONFIG

logger = logging.getLogger(__name__)


class SupabasePublisher:
    """Handles MP3 upload and RSS feed generation via Supabase Storage."""

    def __init__(self) -> None:
        self.client = None
        self.bucket: str = os.getenv("SUPABASE_PODCAST_BUCKET", SUPABASE_CONFIG["bucket"])

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")

        if supabase_url and supabase_key:
            try:
                from supabase import create_client

                self.client = create_client(supabase_url, supabase_key)
                key_type = "secret (RLS bypassed)" if os.getenv("SUPABASE_SECRET_KEY") else "publishable (RLS in effect)"
                logger.info("Supabase client initialized. Key type: %s. Bucket: %s", key_type, self.bucket)

                try:
                    items = self._storage().list("")
                    count = len(items) if items is not None else 0
                    logger.info("Bucket '%s' accessible — %d item(s) at root.", self.bucket, count)
                except Exception as e:
                    logger.warning("Unable to list bucket '%s': %s", self.bucket, e)

            except Exception as e:
                logger.error("Supabase initialization failed: %s", e)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Return True if the Supabase client is configured and ready."""
        return self.client is not None

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    def _storage(self):  # type: ignore[return]
        return self.client.storage.from_(self.bucket)

    def upload_file(
        self, local_path: str, remote_path: str, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload a local file to Supabase Storage and return its public URL."""
        logger.info("Uploading file: %s → %s (content-type: %s)", local_path, remote_path, content_type)
        storage = self._storage()
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            storage.upload(
                path=remote_path,
                file=data,
                file_options={"contentType": content_type, "upsert": "true"},
            )
            url = self._clean_url(storage.get_public_url(remote_path))
            logger.info("Upload successful: %s", url)
            return url
        except Exception as e:
            logger.error("File upload error for '%s': %s", remote_path, e)
            raise

    def upload_bytes(
        self, data: bytes, remote_path: str, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload raw bytes to Supabase Storage and return the public URL."""
        logger.info(
            "Uploading %d bytes → %s (content-type: %s)", len(data), remote_path, content_type
        )
        storage = self._storage()
        try:
            storage.upload(
                path=remote_path,
                file=data,
                file_options={"contentType": content_type, "upsert": "true"},
            )
            url = self._clean_url(storage.get_public_url(remote_path))
            logger.info("Bytes upload successful: %s", url)
            return url
        except Exception as e:
            logger.error("Bytes upload error for '%s': %s", remote_path, e)
            raise

    def download_text(self, remote_path: str) -> str:
        """Download a text file from Supabase Storage and return its content."""
        logger.debug("Downloading text: %s", remote_path)
        storage = self._storage()
        try:
            content = storage.download(remote_path)
            text = content.decode("utf-8") if isinstance(content, bytes) else str(content)
            logger.debug("Downloaded %d characters from '%s'.", len(text), remote_path)
            return text
        except Exception as e:
            logger.warning("Download failed for '%s': %s", remote_path, e)
            return ""

    def file_exists(self, remote_path: str) -> bool:
        """Check whether a file exists in Supabase Storage."""
        storage = self._storage()
        try:
            directory = "/".join(remote_path.split("/")[:-1])
            filename = remote_path.split("/")[-1]
            items = storage.list(directory or "")
            found = any(item.get("name") == filename for item in (items or []))
            logger.debug("Existence check '%s': %s", remote_path, found)
            return found
        except Exception:
            # Fallback: try a download probe
            try:
                storage.download(remote_path)
                return True
            except Exception:
                return False

    @staticmethod
    def _clean_url(url: str) -> str:
        """Strip the trailing '?' that some Supabase SDK versions append."""
        return url.rstrip("?")

    # ------------------------------------------------------------------
    # RSS helpers
    # ------------------------------------------------------------------

    def _create_new_rss_root(self, custom_title: Optional[str] = None) -> ET.Element:
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        channel = ET.SubElement(rss, "channel")
        title = custom_title if custom_title else PODCAST_CONFIG["title"]
        self._append_text(channel, "title", title)
        self._append_text(channel, "link", PODCAST_CONFIG["site_url"])
        self._append_text(channel, "language", PODCAST_CONFIG["language"])
        self._append_text(channel, "description", PODCAST_CONFIG["description"])
        self._append_text(channel, "lastBuildDate", formatdate(localtime=True))
        return rss

    def _append_text(self, parent: ET.Element, tag: str, text: str) -> ET.Element:
        el = ET.SubElement(parent, tag)
        el.text = text
        return el

    def _set_text(self, parent: ET.Element, tag: str, text: str) -> ET.Element:
        el = parent.find(tag)
        if el is None:
            el = ET.SubElement(parent, tag)
        el.text = text
        return el

    def _format_duration_hhmmss(self, seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _build_or_update_rss(
        self,
        mp3_url: str,
        episode_title: str,
        duration_seconds: float,
        existing_xml: str,
        cover_url: Optional[str] = None,
        channel_title: Optional[str] = None,
        file_size: int = 0,
    ) -> bytes:
        """Build a new RSS feed or append an episode item to an existing one."""
        if existing_xml:
            try:
                root = ET.fromstring(existing_xml)
            except ET.ParseError as e:
                logger.error(
                    "Cannot parse existing RSS — aborting to prevent episode loss: %s", e
                )
                raise

        else:
            root = self._create_new_rss_root(channel_title)

        channel = root.find("channel")
        if channel is None:
            root = self._create_new_rss_root(channel_title)
            channel = root.find("channel")
        assert channel is not None  # satisfy type checker

        # Refresh channel metadata
        self._set_text(channel, "title", PODCAST_CONFIG["title"])
        self._set_text(channel, "link", PODCAST_CONFIG["site_url"])
        self._set_text(channel, "language", PODCAST_CONFIG["language"])
        self._set_text(channel, "description", PODCAST_CONFIG["description"])
        self._set_text(channel, "lastBuildDate", formatdate(localtime=True))

        # Build episode item
        item = ET.Element("item")
        self._append_text(item, "title", episode_title)
        self._append_text(item, "description", PODCAST_CONFIG["description"])
        self._append_text(item, "pubDate", formatdate(localtime=True))
        self._append_text(item, "guid", mp3_url)

        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", mp3_url)
        enclosure.set("type", "audio/mpeg")
        enclosure.set("length", str(file_size))

        self._append_text(item, "itunes:duration", self._format_duration_hhmmss(int(duration_seconds)))

        # Cover image
        if cover_url:
            # Remove existing image elements to avoid duplication
            for child in list(channel):
                tag = child.tag
                if tag in ("image",) or "image" in tag:
                    channel.remove(child)

            itunes_img_channel = ET.Element("itunes:image")
            itunes_img_channel.set("href", cover_url)
            channel.append(itunes_img_channel)

            itunes_img_item = ET.Element("itunes:image")
            itunes_img_item.set("href", cover_url)
            item.append(itunes_img_item)

            rss_image = ET.Element("image")
            self._append_text(rss_image, "url", cover_url)
            self._append_text(rss_image, "title", PODCAST_CONFIG["title"])
            self._append_text(rss_image, "link", PODCAST_CONFIG["site_url"])
            channel.append(rss_image)

        channel.append(item)

        if not root.attrib.get("xmlns:itunes"):
            root.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")

        # Pretty-print via minidom
        rough_string = ET.tostring(root, encoding="unicode")
        pretty_xml: bytes = xml.dom.minidom.parseString(rough_string).toprettyxml(
            indent="  ", encoding="utf-8"
        )

        if cover_url:
            if cover_url in pretty_xml.decode("utf-8"):
                logger.debug("Cover image confirmed in RSS output.")
            else:
                logger.warning("Cover image URL not found in RSS output.")

        return pretty_xml

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish_episode(
        self,
        local_mp3_path: str,
        episode_name: str,
        duration_seconds: float,
        podcast_title: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload an MP3 and create/update the RSS feed for a collection.

        Args:
            local_mp3_path: Path to the local MP3 file.
            episode_name:   Filename stem used as the remote path key.
            duration_seconds: Episode duration in seconds.
            podcast_title:  Human-readable episode title for the RSS feed.
            user_id:        Collection/folder name in Supabase Storage.

        Returns:
            Tuple of ``(public_mp3_url, public_rss_url)``.
            Both are ``None`` if Supabase is not configured.
        """
        if not self.is_enabled():
            logger.info("Supabase not configured — skipping upload and RSS generation.")
            return None, None

        collection_folder = f"{user_id}/" if user_id else ""
        logger.info("Publishing to collection: '%s'", collection_folder or "root")

        # 1. Upload MP3
        mp3_remote = f"{collection_folder}{episode_name}.mp3"
        mp3_url = self.upload_file(local_mp3_path, mp3_remote, "audio/mpeg")

        # 2. Resolve cover URL
        cover_url: str = os.getenv(
            "SUPABASE_COVER_URL",
            "https://your-project.supabase.co/storage/v1/object/public/podcasts/cover.png",
        )
        try:
            import requests as _requests

            resp = _requests.head(cover_url, timeout=5)
            if resp.status_code == 200:
                logger.debug("Cover image accessible (HTTP %d).", resp.status_code)
            else:
                logger.warning("Cover image returned HTTP %d — it may not display.", resp.status_code)
        except Exception as e:
            logger.warning("Could not verify cover image accessibility: %s", e)

        # 3. Build / update RSS
        rss_remote = f"{collection_folder}{PODCAST_CONFIG['rss_filename']}"
        existing_xml = ""
        if self.file_exists(rss_remote):
            existing_xml = self.download_text(rss_remote) or ""
        else:
            logger.info("No existing RSS in '%s' — creating a new feed.", collection_folder or "root")

        episode_title = podcast_title if podcast_title else episode_name
        channel_title = podcast_title if podcast_title else PODCAST_CONFIG["title"]
        file_size = os.path.getsize(local_mp3_path)

        rss_bytes = self._build_or_update_rss(
            mp3_url, episode_title, duration_seconds, existing_xml, cover_url, channel_title, file_size
        )
        rss_url = self.upload_bytes(rss_bytes, rss_remote, "application/rss+xml")

        logger.info("Publication complete. RSS: %s | MP3: %s", rss_url, mp3_url)
        return mp3_url, rss_url
