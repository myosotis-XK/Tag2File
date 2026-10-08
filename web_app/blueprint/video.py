"""Authenticated MP4 streaming and SRT conversion for the Web player."""

from html import escape
from pathlib import Path

from flask import Blueprint, current_app, jsonify, make_response, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException

from src.core.subtitles import decode_srt
from web_app.decorators import api_login_required, login_required


video_page_bp = Blueprint('video_page', __name__)
video_api_bp = Blueprint('video_api', __name__)
MAX_SUBTITLE_BYTES = 8 * 1024 * 1024


def _video_path(value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('缺少有效的视频路径')
    path = value.replace('\\', '/')
    if not Path(path).is_absolute() or Path(path).suffix.lower() != '.mp4':
        raise ValueError('仅支持 MP4 视频')
    db_path = current_app.config['VIDEO_GET_USER_SETTING'](session.get('user_id'), 'database_path')
    if not db_path:
        return None
    current_app.config['VIDEO_LOAD_TAGBASE'](db_path)
    data_api = current_app.config['VIDEO_TAGBASE_DATA_DICT'][db_path]
    # Match /open_file's access rule; a sidecar is authorized through its video.
    if not data_api.query('file', path, 'tag'):
        return None
    if not Path(path).is_file():
        raise FileNotFoundError('视频不存在或已移动')
    return Path(path)


def _timestamp(milliseconds):
    seconds, fraction = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}.{fraction:03}'


def _subtitle_response(data, name):
    if len(data) > MAX_SUBTITLE_BYTES:
        return jsonify(message='字幕文件不能超过 8 MB'), 413
    try:
        track = decode_srt(data)
    except (ValueError, UnicodeError):
        return jsonify(message='无法解析 SRT，请检查时间格式和文字编码'), 422
    blocks = [f'{_timestamp(cue.start)} --> {_timestamp(cue.end)}\n{escape(cue.text)}'
              for cue in track.cues]
    return jsonify(exists=True, name=name, content='WEBVTT\n\n' + '\n\n'.join(blocks) + '\n',
                   skipped_blocks=track.skipped_blocks)


@video_page_bp.get('/player')
@login_required
def video_player():
    response = make_response(render_template('video_player.html'))
    response.headers['Cache-Control'] = 'no-store'
    return response


@video_api_bp.errorhandler(ValueError)
def invalid_request(error):
    return jsonify(message=str(error)), 400


@video_api_bp.errorhandler(FileNotFoundError)
def missing_file(error):
    return jsonify(message=str(error)), 404


@video_api_bp.errorhandler(OSError)
def unreadable_file(error):
    current_app.logger.warning('Video file could not be read: %s', error)
    return jsonify(message='无法读取文件，请检查文件状态'), 404


@video_api_bp.errorhandler(HTTPException)
def http_error(error):
    return jsonify(message=error.description), error.code


@video_api_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-cache' if request.endpoint == 'video_api.stream' else 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@video_api_bp.get('/stream')
@api_login_required
def stream():
    path = _video_path(request.args.get('path'))
    if path is None:
        return jsonify(message='当前标签库无权访问此视频'), 403
    # Byte ranges and HEAD support allow seeking without reading the whole file.
    return send_file(path, mimetype='video/mp4', conditional=True, as_attachment=False)


@video_api_bp.route('/subtitles', methods=['GET', 'POST'])
@api_login_required
def subtitles():
    if request.method == 'POST':
        request.max_content_length = MAX_SUBTITLE_BYTES + 65536
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return jsonify(message='无效的字幕请求'), 403
    value = request.form.get('path') if request.method == 'POST' else request.args.get('path')
    path = _video_path(value)
    if path is None:
        return jsonify(message='当前标签库无权访问此视频'), 403
    if request.method == 'POST':
        uploaded = request.files.get('file')
        if not uploaded or Path(uploaded.filename or '').suffix.lower() != '.srt':
            raise ValueError('请选择 SRT 字幕文件')
        return _subtitle_response(uploaded.stream.read(MAX_SUBTITLE_BYTES + 1),
                                  (uploaded.filename or '').replace('\\', '/').split('/')[-1])
    sidecar = path.with_suffix('.srt')
    if not sidecar.is_file():
        return jsonify(exists=False)
    with sidecar.open('rb') as source:
        return _subtitle_response(source.read(MAX_SUBTITLE_BYTES + 1), sidecar.name)
