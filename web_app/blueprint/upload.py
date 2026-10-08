"""Upload files into an existing folder without replacing existing entries."""

import os
import re

from flask import Blueprint, current_app, jsonify, request

from web_app.decorators import api_login_required


upload_api_bp = Blueprint('upload_api', __name__)


def valid_filename(name):
    # Keep Unicode names, but reject paths, Windows device names and ADS syntax.
    if not name or name in {'.', '..'} or name.endswith((' ', '.')):
        return False
    if any(ord(char) < 32 or char in '/\\<>:"|?*' for char in name):
        return False
    stem = name.split('.')[0].rstrip(' ').upper()
    return not re.fullmatch(r'CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³]', stem)


@upload_api_bp.route('/upload_file', methods=['POST'])
@api_login_required
def upload_file():
    # A custom header prevents cross-origin HTML forms from writing files.
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify(success=False, message='无效的上传请求'), 403

    folder = request.form.get('folder_path', '')
    files = request.files.getlist('file')
    if not folder or not os.path.isabs(folder):
        return jsonify(success=False, message='请指定有效的绝对文件夹路径'), 400
    if len(files) != 1 or not valid_filename(files[0].filename):
        return jsonify(success=False, message='请选择一个文件，文件名不能包含路径或非法字符'), 400
    folder = os.path.realpath(folder)
    if not os.path.isdir(folder):
        return jsonify(success=False, message='目标文件夹不存在'), 404

    uploaded = files[0]
    target = os.path.join(folder, uploaded.filename)
    created = False
    try:
        # Exclusive creation also protects existing directories and symlinks.
        with open(target, 'xb') as destination:
            created = True
            uploaded.save(destination)
    except FileExistsError:
        return jsonify(success=False, message='同名文件或文件夹已存在，未覆盖'), 409
    except OSError:
        # Windows reports an existing directory as PermissionError.
        if not created and os.path.lexists(target):
            return jsonify(success=False, message='同名文件或文件夹已存在，未覆盖'), 409
        if created:
            try:
                os.unlink(target)
            except OSError:
                current_app.logger.exception('Could not remove incomplete upload')
        current_app.logger.exception('File upload failed')
        return jsonify(success=False, message='保存失败，请检查文件夹写入权限和磁盘空间'), 500

    return jsonify(success=True, file_name=uploaded.filename,
                   file_path=target.replace('\\', '/')), 201
