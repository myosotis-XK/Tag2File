"""Compatibility imports for the shared desktop and Web subtitle parser."""

from src.core.subtitles import SubtitleCue, SubtitleTrack, decode_srt, load_srt, parse_srt

__all__ = ['SubtitleCue', 'SubtitleTrack', 'decode_srt', 'load_srt', 'parse_srt']
