from PyQt5.QtCore import QTime


AUDIO_FILE_EXTENSIONS = {
    '.mp3',
    '.wav',
    '.flac',
    '.m4a',
    '.aac',
    '.ogg',
    '.wma',
    '.ape',
}


def format_time(ms):
    """Format milliseconds as mm:ss."""
    time_value = QTime(0, 0).addMSecs(max(0, ms or 0))
    return time_value.toString("mm:ss")


def normalize_audio_path(path):
    return path.replace('\\', '/') if path else path


def marker_sort_key(marker):
    if marker.get('type') == 0:
        return marker.get('time', 0)
    return marker.get('start', 0)


def sort_markers(markers):
    return sorted(markers, key=marker_sort_key)


def marker_display_text(marker):
    if marker.get('type') == 0:
        return f"{format_time(marker.get('time', 0))} - {marker.get('label', '')}"

    start_text = format_time(marker.get('start', 0))
    end_text = format_time(marker.get('end', 0))
    return f"{start_text}-{end_text} - {marker.get('label', '')}"


def marker_tooltip_text(marker):
    label = marker.get('label', '')
    if marker.get('type') == 0:
        return f"{label} - {format_time(marker.get('time', 0))}"

    start_text = format_time(marker.get('start', 0))
    end_text = format_time(marker.get('end', 0))
    return f"{label} - {start_text}~{end_text}"


def marker_jump_position(marker):
    if marker.get('type') == 0:
        return marker.get('time', 0)
    return marker.get('start', 0)
