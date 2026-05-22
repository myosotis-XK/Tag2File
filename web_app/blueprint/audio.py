import os

from flask import Blueprint, current_app, jsonify, make_response, render_template, request, session
from web_app.decorators import login_required


audio_page_bp = Blueprint('audio_page', __name__)
audio_api_bp = Blueprint('audio_api', __name__)


def get_audio_dependencies():
    get_user_setting = current_app.config['AUDIO_GET_USER_SETTING']
    tagbase_data_dict = current_app.config['AUDIO_TAGBASE_DATA_DICT']
    db_path = get_user_setting(session.get('user_id'), 'database_path')
    return get_user_setting, tagbase_data_dict, tagbase_data_dict[db_path]


def sort_markers(markers):
    return sorted(markers, key=lambda marker: marker.get('start', marker.get('time', 0)))


@audio_page_bp.route('/player', methods=['GET'])
@login_required
def audio_player():
    response = make_response(render_template('audio_player.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@audio_api_bp.route('/metadata', methods=['POST'])
@login_required
def get_audio_metadata():
    try:
        data = request.get_json() or {}
        file_paths = data.get('file_paths', [])
        if not file_paths:
            return jsonify({'error': '缺少file_paths参数'}), 400

        _get_user_setting, _tagbase_data_dict, data_api = get_audio_dependencies()
        metadata_list = []

        for file_path in file_paths:
            normalized_path = file_path.replace('\\', '/')
            filename = os.path.basename(normalized_path)
            title = os.path.splitext(filename)[0]
            lyric_path = os.path.splitext(file_path)[0] + '.lrc'
            markers = sort_markers(data_api.get_audio_markers(normalized_path))

            metadata_list.append({
                'path': normalized_path,
                'title': title,
                'has_lyric': os.path.exists(lyric_path),
                'markers': markers,
            })

        return jsonify({'metadata': metadata_list})
    except Exception as error:
        print(f'获取音频元数据错误: {error}')
        return jsonify({'error': str(error)}), 500


@audio_api_bp.route('/lyric', methods=['GET'])
@login_required
def get_audio_lyric():
    try:
        audio_path = request.args.get('audio_path')
        if not audio_path:
            return jsonify({'error': '缺少audio_path参数'}), 400

        lyric_path = os.path.splitext(audio_path)[0] + '.lrc'
        if not os.path.exists(lyric_path):
            return jsonify({'exists': False, 'content': ''})

        with open(lyric_path, 'r', encoding='utf-8') as file_obj:
            content = file_obj.read()

        return jsonify({'exists': True, 'content': content})
    except Exception as error:
        print(f'获取歌词错误: {error}')
        return jsonify({'error': str(error)}), 500


@audio_api_bp.route('/markers', methods=['POST'])
@login_required
def add_or_update_marker():
    try:
        data = request.get_json() or {}
        file_path = data.get('file_path')
        marker = data.get('marker')

        if not file_path or not marker:
            return jsonify({'error': '缺少必要参数'}), 400

        _get_user_setting, _tagbase_data_dict, data_api = get_audio_dependencies()
        normalized_path = file_path.replace('\\', '/')
        marker_id = marker.get('id')
        marker['time'] = int(marker.get('time', 0))
        marker['start'] = int(marker.get('start', 0))
        marker['end'] = int(marker.get('end', 0))

        if marker_id:
            data_api.update_audio_marker(normalized_path, marker_id, marker)
        else:
            data_api.add_audio_marker(normalized_path, marker)

        updated_markers = sort_markers(data_api.get_audio_markers(normalized_path))
        return jsonify({'success': True, 'markers': updated_markers})
    except Exception as error:
        print(f'添加/更新标记错误: {error}')
        return jsonify({'success': False, 'error': str(error)}), 500


@audio_api_bp.route('/markers/<int:marker_id>', methods=['DELETE'])
@login_required
def delete_marker(marker_id):
    try:
        file_path = request.args.get('file_path')
        if not file_path:
            return jsonify({'error': '缺少file_path参数'}), 400

        _get_user_setting, _tagbase_data_dict, data_api = get_audio_dependencies()
        normalized_path = file_path.replace('\\', '/')
        data_api.delete_audio_marker(normalized_path, marker_id)

        updated_markers = sort_markers(data_api.get_audio_markers(normalized_path))
        return jsonify({'success': True, 'markers': updated_markers})
    except Exception as error:
        print(f'删除标记错误: {error}')
        return jsonify({'success': False, 'error': str(error)}), 500


@audio_api_bp.route('/marker_presets', methods=['GET'])
@login_required
def get_marker_presets():
    try:
        _get_user_setting, _tagbase_data_dict, data_api = get_audio_dependencies()
        presets = data_api.get_all_marker_presets()
        result = [
            {
                'id': preset_id,
                'name': name,
                'color': color,
                'order_index': order_index,
            }
            for preset_id, name, color, order_index in presets
        ]
        return jsonify({'success': True, 'presets': result})
    except Exception as error:
        print(f'获取标记预设错误: {error}')
        return jsonify({'success': False, 'error': str(error)}), 500
