import os
from typing import Optional, Tuple
from email.utils import formatdate
import xml.etree.ElementTree as ET

from config import PODCAST_CONFIG, SUPABASE_CONFIG


class SupabasePublisher:
    def __init__(self) -> None:
        self.client = None
        self.bucket = SUPABASE_CONFIG["bucket"]

        # Environment variables loading
        supabase_url = os.getenv("SUPABASE_URL")
        # Preference for service key if available (bypass RLS). Otherwise ANON.
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                self.client = create_client(supabase_url, supabase_key)
                print("[Supabase] Client initialized.")
                print(f"[Supabase] Target bucket: {self.bucket}")
                if os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
                    print("[Supabase] Service key detected (RLS bypassed server-side).")
                else:
                    print("[Supabase] Using ANON key (RLS in effect).")
                # Bucket verification
                try:
                    storage = self._storage()
                    items = storage.list("")
                    count = len(items) if items is not None else 0
                    print(f"[Supabase] Bucket '{self.bucket}' is accessible. {count} items at root.")
                except Exception as e:
                    print(f"[Supabase] ⚠️  Unable to list bucket '{self.bucket}': {e}")
            except Exception as e:
                print(f"⚠️  Supabase initialization failed: {e}")

    def is_enabled(self) -> bool:
        return self.client is not None

    # ---------- Storage helpers ----------
    def _storage(self):
        return self.client.storage.from_(self.bucket)

    def upload_file(self, local_path: str, remote_path: str, content_type: str = "application/octet-stream") -> str:
        print(f"[Supabase] Upload file → {local_path} -> {remote_path} (type={content_type})")
        storage = self._storage()
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            # Some clients expect bytes directly
            storage.upload(path=remote_path, file=data, file_options={"contentType": content_type, "upsert": "true"})
            url = storage.get_public_url(remote_path)
            # Clean URL by removing final question mark added by Supabase
            if url.endswith('?'):
                url = url[:-1]
            print(f"[Supabase] ✓ Upload successful: {url}")
            return url
        except Exception as e:
            print(f"[Supabase] ❌ File upload error '{remote_path}': {e}")
            raise

    def upload_bytes(self, data: bytes, remote_path: str, content_type: str = "application/octet-stream") -> str:
        print(f"[Supabase] Upload bytes → {remote_path} (type={content_type}, {len(data)} bytes)")
        storage = self._storage()
        try:
            storage.upload(path=remote_path, file=data, file_options={"contentType": content_type, "upsert": "true"})
            url = storage.get_public_url(remote_path)
            # Clean URL by removing final question mark added by Supabase
            if url.endswith('?'):
                url = url[:-1]
            print(f"[Supabase] ✓ Bytes upload successful: {url}")
            return url
        except Exception as e:
            print(f"[Supabase] ❌ Bytes upload error '{remote_path}': {e}")
            raise

    def download_text(self, remote_path: str) -> str:
        print(f"[Supabase] Download text ← {remote_path}")
        storage = self._storage()
        try:
            content = storage.download(remote_path)
            if isinstance(content, bytes):
                txt = content.decode("utf-8")
            else:
                try:
                    txt = content.decode("utf-8")
                except Exception:
                    txt = str(content)
            print(f"[Supabase] ✓ Text download {len(txt)} characters")
            return txt
        except Exception as e:
            print(f"[Supabase] ⚠️  Download failed '{remote_path}': {e}")
            return ""

    def file_exists(self, remote_path: str) -> bool:
        # Attempt: list directory and check name
        storage = self._storage()
        try:
            directory = "/".join(remote_path.split("/")[:-1])
            filename = remote_path.split("/")[-1]
            items = storage.list(directory or "")
            found = any(item.get("name") == filename for item in items)
            print(f"[Supabase] Existence '{remote_path}' via list('{directory or '/'}'): {found}")
            return found
        except Exception:
            # Fallback: try a download
            try:
                _ = storage.download(remote_path)
                print(f"[Supabase] Fallback existence by download OK for '{remote_path}'")
                return True
            except Exception:
                print(f"[Supabase] Fallback existence by download KO for '{remote_path}'")
                return False

    # ---------- RSS helpers ----------
    def _create_new_rss_root(self, custom_title: str = None) -> ET.Element:
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

    def _append_text(self, parent: ET.Element, tag: str, text: str):
        el = ET.SubElement(parent, tag)
        el.text = text

    def _set_text(self, parent: ET.Element, tag: str, text: str):
        el = parent.find(tag)
        if el is None:
            el = ET.SubElement(parent, tag)
        el.text = text

    def _format_duration_hhmmss(self, seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _build_or_update_rss(self, mp3_url: str, episode_title: str, duration_seconds: float, existing_xml: str, cover_url: Optional[str] = None, channel_title: str = None) -> bytes:
        if existing_xml:
            try:
                root = ET.fromstring(existing_xml)
            except Exception:
                root = self._create_new_rss_root(channel_title)
        else:
            root = self._create_new_rss_root(channel_title)

        channel = root.find("channel")
        if channel is None:
            root = self._create_new_rss_root(channel_title)
            channel = root.find("channel")

        # Update channel metadata
        self._set_text(channel, "title", PODCAST_CONFIG["title"])
        self._set_text(channel, "link", PODCAST_CONFIG["site_url"])
        self._set_text(channel, "language", PODCAST_CONFIG["language"])
        self._set_text(channel, "description", PODCAST_CONFIG["description"])
        self._set_text(channel, "lastBuildDate", formatdate(localtime=True))


        # Add item
        item = ET.Element("item")
        self._append_text(item, "title", episode_title)
        self._append_text(item, "description", PODCAST_CONFIG["description"])
        self._append_text(item, "pubDate", formatdate(localtime=True))
        self._append_text(item, "guid", mp3_url)


        enclosure = ET.Element("enclosure")
        enclosure.set("url", mp3_url)
        enclosure.set("type", "audio/mpeg")
        enclosure.set("length", "0")
        item.append(enclosure)

        duration_str = self._format_duration_hhmmss(int(duration_seconds))
        self._append_text(item, "itunes:duration", duration_str)

        # Add cover image (hardcoded URL)
        if cover_url:
            # Image for iTunes (channel)
            itunes_image_channel = ET.Element("itunes:image")
            itunes_image_channel.set("href", cover_url)
            channel.append(itunes_image_channel)
            
            # Image for iTunes (episode)
            itunes_image_item = ET.Element("itunes:image")
            itunes_image_item.set("href", cover_url)
            item.append(itunes_image_item)
            
            # Standard RSS image (channel)
            image_channel = ET.Element("image")
            self._append_text(image_channel, "url", cover_url)
            self._append_text(image_channel, "title", PODCAST_CONFIG["title"])
            self._append_text(image_channel, "link", PODCAST_CONFIG["site_url"])
            channel.append(image_channel)

        # Insert item after adding image
        channel.append(item)

        if not root.attrib.get("xmlns:itunes"):
            root.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")

        xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        
        # Verify that image is in RSS
        if cover_url:
            xml_str = xml_bytes.decode('utf-8')
            if 'itunes:image' in xml_str and 'href="' + cover_url + '"' in xml_str:
                print(f"✅ Cover image integrated in RSS")
            else:
                print(f"⚠️  Cover image missing in RSS")
        
        return xml_bytes

    # ---------- Public API ----------
    def publish_episode(self, local_mp3_path: str, episode_name: str, duration_seconds: float, podcast_title: str = None, user_id: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Publishes an episode: upload MP3, create/update RSS.
        Returns (public_mp3_url, public_rss_url). None if Supabase disabled.
        user_id is now used as folder/collection name in Supabase.
        """
        if not self.is_enabled():
            print("ℹ️  Supabase not configured: upload and RSS ignored")
            return None, None

        # Use user_id as folder/collection name
        collection_folder = f"{user_id}/" if user_id else ""
        print(f"📁 Collection/Folder: {collection_folder or 'root'}")
        
        # 1) Upload MP3 to collection folder
        mp3_remote = f"{collection_folder}{episode_name}.mp3"
        mp3_url = self.upload_file(local_mp3_path, mp3_remote, "audio/mpeg")
        print(f"✓ MP3 uploaded to Supabase: {mp3_url}")

        # 2) Cover image URL (configure according to your Supabase instance)
        cover_url = os.getenv("SUPABASE_COVER_URL", "https://your-project.supabase.co/storage/v1/object/public/podcasts/cover.png")
        print(f"ℹ️  Cover image: {cover_url}")
        
        # Verify that image is accessible
        try:
            import requests
            response = requests.head(cover_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Cover image accessible: {response.status_code}")
            else:
                print(f"⚠️  Cover image not accessible: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Unable to verify cover image: {e}")

        # 3) Build or create RSS in user folder
        rss_remote = f"{collection_folder}{PODCAST_CONFIG['rss_filename']}"
        existing_xml = ""
        if self.file_exists(rss_remote):
            existing_xml = self.download_text(rss_remote) or ""
        else:
            print(f"ℹ️  No RSS found in folder {collection_folder}, creating new feed…")

        # Use custom podcast title if available, otherwise episode name
        episode_title = podcast_title if podcast_title else episode_name
        # Channel title: use podcast key or default title
        channel_title = podcast_title if podcast_title else PODCAST_CONFIG["title"]
        rss_bytes = self._build_or_update_rss(mp3_url, episode_title, duration_seconds, existing_xml, cover_url, channel_title)
        rss_url = self.upload_bytes(rss_bytes, rss_remote, "application/rss+xml")
        print(f"✓ RSS updated/uploaded: {rss_url}")

        # 4) Useful final log
        print("— Supabase publication completed —")
        print(f"Public RSS: {rss_url}")
        print(f"Public MP3: {mp3_url}")
        if cover_url:
            print(f"Cover image: {cover_url}")
        return mp3_url, rss_url


