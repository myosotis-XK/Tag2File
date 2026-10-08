"""External access to the tagbase's global manual file order."""

import sqlite3

from flask import Blueprint, current_app, jsonify, request

from src.core.DictManage import ManualOrderFileNotFoundError
from web_app.decorators import api_login_required


manual_order_api_bp = Blueprint('manual_order_api', __name__)


def _request_data():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('请求体必须是 JSON 对象')
    db_path = data.get('db_path')
    if not isinstance(db_path, str) or not db_path.strip():
        raise ValueError('数据库路径必须是非空字符串')
    paths = data.get('file_paths')
    if not isinstance(paths, list) or not paths:
        raise ValueError('文件列表必须是非空数组')
    if any(not isinstance(path, str) or not path.strip() for path in paths):
        raise ValueError('文件列表中的路径必须是非空字符串')
    paths = [path.replace('\\', '/') for path in paths]
    if len(set(paths)) != len(paths):
        raise ValueError('文件列表不能包含重复路径')
    return data, db_path, paths


def _data_api(db_path):
    current_app.config['MANUAL_ORDER_LOAD_TAGBASE'](db_path)
    return current_app.config['MANUAL_ORDER_TAGBASE_DATA_DICT'][db_path]


def _committed_response(changes, *, missing_file_paths=None):
    affected = [path for action, payload in changes.file_events if action == 'manual_order_changed'
                for path in payload['file_paths']]
    if affected:
        publish = current_app.config.get('PUBLISH_TAGBASE_CHANGES')
        if publish is not None:
            publish(changes)
    result = dict(success=True, changed=bool(affected), affected_count=len(affected))
    if missing_file_paths is not None:
        result['missing_file_paths'] = missing_file_paths
    return jsonify(result)


@manual_order_api_bp.errorhandler(ValueError)
def invalid_request(error):
    return jsonify(success=False, error='invalid_request', message=str(error)), 400


@manual_order_api_bp.errorhandler(ManualOrderFileNotFoundError)
def missing_file(error):
    return jsonify(success=False, error='file_not_found', message=str(error)), 404


@manual_order_api_bp.errorhandler(FileNotFoundError)
def missing_tagbase(error):
    return jsonify(success=False, error='tagbase_not_found', message='标签库不存在'), 404


@manual_order_api_bp.errorhandler(sqlite3.Error)
def database_error(error):
    current_app.logger.exception('Manual order database operation failed')
    return jsonify(success=False, error='database_error', message='数据库操作失败，请重试'), 500


@manual_order_api_bp.route('/query', methods=['POST'])
@api_login_required
def query_manual_order():
    _data, db_path, paths = _request_data()
    ordered = _data_api(db_path).get_manual_file_order(paths, use_cache=False)
    known = set(ordered)
    missing = [path for path in paths if path not in known]
    return jsonify(success=True, file_paths=ordered, missing_file_paths=missing)


@manual_order_api_bp.route('/move', methods=['POST'])
@api_login_required
def move_manual_order():
    data, db_path, paths = _request_data()
    target = data.get('target')
    if not isinstance(target, str) or not target.strip():
        raise ValueError('目标文件路径必须是非空字符串')
    placement = data.get('placement')
    if not isinstance(placement, str) or placement not in {'before', 'after'}:
        raise ValueError('placement 必须是 before 或 after')
    changes = _data_api(db_path).move_files_manually(paths, target, placement)
    return _committed_response(changes)


@manual_order_api_bp.route('/set', methods=['POST'])
@api_login_required
def set_manual_order():
    _data, db_path, paths = _request_data()
    changes = _data_api(db_path).set_manual_file_order(paths, strict=False)
    return _committed_response(changes, missing_file_paths=changes.missing_file_paths)
