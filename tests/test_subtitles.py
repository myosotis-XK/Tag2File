"""SRT parsing, encoding and overlapping cue timing."""

from pathlib import Path
import tempfile
import unittest

from src.ui.media_viewers.video.subtitles import load_srt, parse_srt


class SubtitleTests(unittest.TestCase):
    def test_multiline_bom_crlf_and_exact_start_end(self):
        track = parse_srt('\ufeff1\r\n00:00:05,000 --> 00:00:08,000\r\n中文\r\nEnglish\r\n')
        self.assertEqual(track.text_at(4999), '')
        self.assertEqual(track.text_at(5000), '中文\nEnglish')
        self.assertEqual(track.text_at(7999), '中文\nEnglish')
        self.assertEqual(track.text_at(8000), '')

    def test_unsorted_overlapping_cues_and_random_seeks(self):
        track = parse_srt('2\n00:00:02,000 --> 00:00:03,000\nSecond\n\n'
                          '1\n00:00:01,000 --> 00:00:05,000\nFirst\n\n'
                          '3\n00:00:06,000 --> 00:00:07,000\nThird')
        for time, text in [(6500, 'Third'), (2000, 'First\nSecond'), (3000, 'First'),
                           (5000, ''), (1000, 'First'), (0, ''), (7000, '')]:
            self.assertEqual(track.text_at(time), text)

    def test_optional_number_hours_dot_fraction_and_basic_markup(self):
        track = parse_srt('01:02:03.50 --> 01:02:04.125\n<b>A &amp; B</b><br /><i>第二行</i>')
        self.assertEqual(track.text_at(3723500), 'A & B\n第二行')
        self.assertEqual(track.text_at(3724125), '')

    def test_unsupported_html_is_literal_never_rendered(self):
        track = parse_srt('1\n00:00:00,000 --> 00:00:01,000\n<img src="https://example.com/a.png">')
        self.assertEqual(track.text_at(0), '<img src="https://example.com/a.png">')

    def test_invalid_blocks_are_skipped_without_discarding_valid_cues(self):
        track = parse_srt('1\n00:00:09,000 --> 00:00:01,000\nReversed\n\n'
                          '2\n00:61:00,000 --> 00:62:00,000\nInvalid\n\n'
                          '3\n00:00:02,000 --> 00:00:03,000\nValid')
        self.assertEqual(track.skipped_blocks, 2)
        self.assertEqual(track.text_at(2000), 'Valid')

    def test_invalid_or_empty_file_is_reported(self):
        for text in ('', 'garbage', '1\n00:00:01,000 --> 00:00:01,000\nEmpty duration'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_srt(text)

    def test_utf8_utf16_and_chinese_legacy_encoding(self):
        text = '1\n00:00:00,000 --> 00:00:01,000\n字幕测试'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '字幕.srt'
            for encoding in ('utf-8', 'utf-8-sig', 'utf-16', 'gb18030'):
                with self.subTest(encoding=encoding):
                    path.write_bytes(text.encode(encoding))
                    self.assertEqual(load_srt(path).text_at(0), '字幕测试')


if __name__ == '__main__':
    unittest.main()
