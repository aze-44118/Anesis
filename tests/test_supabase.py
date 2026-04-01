"""
Tests for SupabasePublisher — RSS building, duration formatting, and disabled state.
No real Supabase connection is used.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from supabase_client import SupabasePublisher  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def publisher() -> SupabasePublisher:
    """Return a SupabasePublisher with no Supabase credentials (disabled state)."""
    with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SECRET_KEY": "", "SUPABASE_PUBLISHABLE_KEY": ""}, clear=False):
        return SupabasePublisher()


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------

class TestIsEnabled:
    def test_disabled_without_credentials(self, publisher: SupabasePublisher) -> None:
        assert publisher.is_enabled() is False

    def test_publish_returns_none_tuple_when_disabled(self, publisher: SupabasePublisher) -> None:
        mp3_url, rss_url = publisher.publish_episode(
            "/tmp/fake.mp3", "test_episode", 120.0, "Test", "collection"
        )
        assert mp3_url is None
        assert rss_url is None


# ---------------------------------------------------------------------------
# _format_duration_hhmmss
# ---------------------------------------------------------------------------

class TestFormatDuration:
    def test_minutes_and_seconds(self, publisher: SupabasePublisher) -> None:
        assert publisher._format_duration_hhmmss(90) == "01:30"

    def test_hours_minutes_seconds(self, publisher: SupabasePublisher) -> None:
        assert publisher._format_duration_hhmmss(3661) == "01:01:01"

    def test_zero(self, publisher: SupabasePublisher) -> None:
        assert publisher._format_duration_hhmmss(0) == "00:00"

    def test_exactly_one_hour(self, publisher: SupabasePublisher) -> None:
        assert publisher._format_duration_hhmmss(3600) == "01:00:00"


# ---------------------------------------------------------------------------
# _build_or_update_rss
# ---------------------------------------------------------------------------

class TestBuildOrUpdateRSS:
    def test_creates_new_feed_when_no_existing_xml(self, publisher: SupabasePublisher) -> None:
        rss_bytes = publisher._build_or_update_rss(
            mp3_url="https://example.com/ep1.mp3",
            episode_title="Episode 1",
            duration_seconds=300.0,
            existing_xml="",
            file_size=1024,
        )
        xml_str = rss_bytes.decode("utf-8")
        assert "<rss" in xml_str
        assert "<channel>" in xml_str or "<channel" in xml_str
        assert "Episode 1" in xml_str
        assert "ep1.mp3" in xml_str

    def test_appends_item_to_existing_feed(self, publisher: SupabasePublisher) -> None:
        # Build first episode
        first = publisher._build_or_update_rss(
            mp3_url="https://example.com/ep1.mp3",
            episode_title="Episode 1",
            duration_seconds=300.0,
            existing_xml="",
            file_size=1024,
        )
        # Append second episode
        second = publisher._build_or_update_rss(
            mp3_url="https://example.com/ep2.mp3",
            episode_title="Episode 2",
            duration_seconds=600.0,
            existing_xml=first.decode("utf-8"),
            file_size=2048,
        )
        root = ET.fromstring(second)
        items = root.findall(".//item")
        assert len(items) == 2

    def test_output_is_valid_xml(self, publisher: SupabasePublisher) -> None:
        rss_bytes = publisher._build_or_update_rss(
            mp3_url="https://example.com/ep.mp3",
            episode_title="Test Episode",
            duration_seconds=120.0,
            existing_xml="",
            file_size=512,
        )
        # Should not raise
        ET.fromstring(rss_bytes)

    def test_includes_cover_url_when_provided(self, publisher: SupabasePublisher) -> None:
        cover_url = "https://example.com/cover.png"
        rss_bytes = publisher._build_or_update_rss(
            mp3_url="https://example.com/ep.mp3",
            episode_title="With Cover",
            duration_seconds=180.0,
            existing_xml="",
            cover_url=cover_url,
            file_size=768,
        )
        assert cover_url.encode() in rss_bytes

    def test_raises_on_invalid_existing_xml(self, publisher: SupabasePublisher) -> None:
        with pytest.raises(ET.ParseError):
            publisher._build_or_update_rss(
                mp3_url="https://example.com/ep.mp3",
                episode_title="Bad XML",
                duration_seconds=60.0,
                existing_xml="<not valid xml><<",
                file_size=0,
            )
