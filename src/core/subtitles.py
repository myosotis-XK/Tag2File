"""SRT decoding and time lookup, independent of the video renderer."""

from bisect import bisect_right
from dataclasses import dataclass
from html import unescape
from pathlib import Path
import re


_TIME = r'\d{2,}:[0-5]\d:[0-5]\d[,\.]\d{1,3}'
_TIMING = re.compile(rf'^\s*({_TIME})\s*-->\s*({_TIME})(?:[ \t]+.*)?$')


def _milliseconds(value):
    hours, minutes, seconds, fraction = re.split(r'[:,\.]', value)
    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(fraction.ljust(3, '0'))


def _plain_text(value):
    # SRT formatting is displayed in our uniform style. Never interpret arbitrary HTML.
    value = re.sub(r'<br\s*/?>', '\n', value, flags=re.IGNORECASE)
    value = re.sub(r'</?(?:b|i|u|font)(?:\s+[^<>]*)?>', '', value, flags=re.IGNORECASE)
    return unescape(value).strip()


@dataclass(frozen=True)
class SubtitleCue:
    start: int
    end: int
    text: str


class SubtitleTrack:
    def __init__(self, cues, skipped_blocks=0):
        self.cues = sorted(cues, key=lambda cue: cue.start)
        self.skipped_blocks = skipped_blocks
        self._starts = [cue.start for cue in self.cues]
        self._max_ends = []
        maximum = 0
        for cue in self.cues:
            maximum = max(maximum, cue.end)
            self._max_ends.append(maximum)

    def text_at(self, milliseconds):
        index = bisect_right(self._starts, milliseconds) - 1
        active = []
        # Prefix maxima retain earlier overlapping cues, including after a backward seek.
        while index >= 0 and self._max_ends[index] > milliseconds:
            cue = self.cues[index]
            if milliseconds < cue.end:
                active.append(cue.text)
            index -= 1
        return '\n'.join(reversed(active))


def parse_srt(text):
    cues, skipped = [], 0
    text = text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    for block in re.split(r'\n[ \t]*\n', text.strip()):
        lines = block.strip().splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        match = _TIMING.fullmatch(lines[0]) if lines else None
        if not match or len(lines) < 2:
            skipped += 1
            continue
        start, end = map(_milliseconds, match.groups())
        caption = _plain_text('\n'.join(lines[1:]))
        if end <= start or not caption:
            skipped += 1
            continue
        cues.append(SubtitleCue(start, end, caption))
    if not cues:
        raise ValueError('未找到有效的 SRT 字幕，请检查时间格式和文件内容。')
    return SubtitleTrack(cues, skipped)


def load_srt(path):
    return decode_srt(Path(path).read_bytes())


def decode_srt(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = data.decode('utf-16')
    else:
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Common Chinese subtitle files are GBK; GB18030 includes that character set.
            text = data.decode('gb18030')
    return parse_srt(text)
