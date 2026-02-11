import os
import json
import mimetypes
import warnings
import traceback
import urllib.parse
from flask import Flask, Response, request, session, g, \
send_file, render_template, render_template_string, send_from_directory, jsonify, make_response, abort, redirect, url_for
from PIL import Image
from io import BytesIO
from functools import wraps
from PyQt5.QtWidgets import QFileIconProvider
from PyQt5.QtCore import QFileInfo, QSize, QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QIcon
from src.utils import get_cache_path, root, config, thumbnailExtractor

warnings.filterwarnings('ignore')

TEMPLATES_DIR = os.path.join(root, "web_app", "frontend", "templates")
STATIC_DIR = os.path.join(root, "web_app", "frontend", "static")
app = Flask(
    "tag2file",
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)
app.json.ensure_ascii = False



app.secret_key = 'a_very_secret_key_change_this'  # 用于加密 session cookie

import sqlite3
user_db_path = os.path.join(root, 'web_app', 'users.db')
def get_db():
    """获取数据库连接，每个请求独立"""
    if 'db' not in g:
        g.db = sqlite3.connect(user_db_path)
        # 设置行工厂，返回字典形式的结果
        g.db.row_factory = sqlite3.Row
    return g.db

import hashlib

def get_password_hash(password: str) -> str:
    """使用稳定的哈希算法"""
    return hashlib.sha256(password.encode()).hexdigest()

def loogin_check(username: str, password: str):
    """登录检查函数"""
    password_hash = get_password_hash(password)
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            'SELECT user_id FROM users WHERE username = ? AND password = ?', 
            (username, password_hash)
        )
        result = cursor.fetchone()
        print(f"Login check result: {result}")
        return result['user_id']
    except Exception as e:
        print(f"Database error: {e}")
        return None
    finally:
        cursor.close()

@app.errorhandler(Exception)  
def handle_global_exception(e):  
    # 普通异常，返回 500 状态码  
    status_code = 500  
    error_message = str(e)
    print(status_code)
    print(error_message)
    traceback.print_exc()
    # 构造统一的错误响应  
    response = {  
        "success": False,  
        "error": {  
            "type": e.__class__.__name__,  # 异常类型  
            "message": error_message,      # 异常信息  
        },  
        "status_code": status_code,  
        "path": request.path,             # 请求路径  
        "method": request.method          # 请求方法  
    }
    return jsonify(response), status_code  

import shelve
from src.models.TagClass import get_tag_files

def load_tagbase_data(tagbase_path: str) -> dict:
    """
    加载指定标签库的数据。此函数在 Flask 线程中独立运行，不依赖任何类实例。

    Args:
        tagbase_name: 要加载的标签库文件名（不含扩展名）。

    Returns:
        包含 'relation_graph', 'special_categories', 'special_tags_status' 的字典。
    """
    data = {
        'relation_graph': {},
        'special_categories': [],
        'special_tags_status': {}
    }
    
    try:
        with shelve.open(tagbase_path) as shelf:
            default_category = {
                "未分类": {
                    "tagColor": "#c8c8c8", 
                    "tags": set(), 
                    "tagOrder": []
                }
            }
            
            data['relation_graph']['category'] = shelf.get('category_dict', default_category)
            data['relation_graph']['tag'] = shelf.get('tag_dict', {})
            data['relation_graph']['file'] = shelf.get('file_dict', {})
            data['special_categories'].extend(shelf.get('special_categories', []))
            data['special_tags_status'].update(shelf.get('special_tags_status', {}))
            
    except Exception as e:
        # 在 Web 线程中，打印错误并返回安全响应
        print(f"Error loading tagbase {tagbase_path}: {e}")
        # 如果读取失败，将返回带有空字典的 data
    return data

tagbase_data_dict = {}

_icon_provider = QFileIconProvider()

def qicon_to_pil_image(qicon: QIcon, size: int) -> Image.Image | None:
    """
    将 QIcon 转换为指定大小的 PIL Image 对象。
    """
    # 尝试获取指定大小的 QPixmap
    qsize = QSize(size, size)
    pixmap = qicon.pixmap(qsize)

    if pixmap.isNull():
        return None

    # 将 QPixmap 转换为 QByteArray (PNG格式)
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QIODevice.WriteOnly)
    
    # 将 QPixmap 保存为 PNG 格式到 QBuffer
    # 注意：这里我们强制使用 PNG 格式，因为它支持透明度，与原代码的 save(..., format='PNG') 保持一致
    if not pixmap.save(buffer, "PNG"):
        buffer.close()
        return None
    
    buffer.close()
    
    # 从 QByteArray 创建 BytesIO 对象
    img_byte_array = BytesIO(byte_array.data())
    
    # 使用 PIL 从 BytesIO 加载图像
    try:
        pil_img = Image.open(img_byte_array)
        # 确保返回一个可修改的副本（通常 Image.open 返回的已是，但为了安全）
        return pil_img.copy() 
    except Exception as e:
        print(f"PIL 无法从 QPixmap 数据加载图像: {e}")
        return None


def get_file_icon(file_path: str, size: int) -> Image.Image | None:
    """
    使用 QFileIconProvider 获取文件的系统图标，并转换为 PIL Image。
    
    :param file_path: 文件或文件夹的路径
    :param size: 图标的边长（例如 16, 32, 48 等）
    :return: PIL Image 对象或 None
    """
    if not os.path.exists(file_path):
        return None

    file_info = QFileInfo(file_path)
    
    # 使用全局的 _icon_provider 实例来获取 QIcon
    qicon = _icon_provider.icon(file_info)

    if qicon.isNull():
        return None

    # 将 QIcon 转换为 PIL Image
    pil_img = qicon_to_pil_image(qicon, size)
    
    return pil_img

def get_file_thumb(file_path: str, size: int, use_cache: bool = True):
    """
    根据文件路径和期望的缩略图最大尺寸，生成缩略图的字节流和MIME类型，并支持磁盘缓存。

    Args:
        file_path (str): 待处理的文件路径。
        size (int): 缩略图的最大边长（宽度或高度）。
        use_cache (bool): 是否使用磁盘缓存。

    Returns:
        tuple[BytesIO, str] | tuple[None, None]: 
            包含缩略图字节流的 BytesIO 对象和 MIME 类型 (str)。
            如果文件不存在或处理失败，返回 (None, None)。
    """
    if not os.path.exists(file_path):
        return None, None
    mime_type, _ = mimetypes.guess_type(file_path)
    thumb_data = None
    thumb_mime = None
    size = size*4
    if not mime_type:
        # 尝试获取系统图标
        pil_img = get_file_icon(file_path, size)
        
        if pil_img:
            img_byte_array = BytesIO()
            pil_img.save(img_byte_array, format='PNG') 
            img_byte_array.seek(0)
            
            thumb_data = img_byte_array
            return thumb_data, 'image/png'
        else:
            return None, None

    if mime_type == 'image/gif':
        # --- 特殊处理 GIF 文件 ---
        with Image.open(file_path) as img:
            out = BytesIO()
            # save 时指定 loop=0 强制无限循环
            # save_all=True 确保保留所有帧
            img.save(out, format='GIF', save_all=True, loop=0, disposal=2)
            out.seek(0)
            return out, 'image/gif'
    
    cache_path = get_cache_path(file_path, size)
    
    # 1. 检查磁盘缓存
    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                thumb_data = BytesIO(f.read())
            # 缓存文件我们统一保存为 PNG
            return thumb_data, 'image/png'
        except Exception as e:
            print(f"❌ 缓存文件 {cache_path} 损坏，已忽略: {e}")
            try:
                os.remove(cache_path) # 删除损坏的缓存文件
            except Exception as del_err:
                print(f"无法删除损坏的缓存: {del_err}")

    # 2. 生成缩略图
    try:
        img = thumbnailExtractor.extract_thumbnail(file_path, size)
        if img is None:
            img = get_file_icon(file_path, size)
            if img is None:
                return None, None
        img_byte_array = BytesIO()
        img.save(img_byte_array, format='PNG')
        thumb_data = img_byte_array
        thumb_mime = 'image/png'
                    
    except Exception as e:
        print(f"❌ 生成文件 {file_path} 的缩略图失败: {e}")
        return None, None

    if thumb_data:
        try:
            with open(cache_path, 'wb') as f:
                f.write(thumb_data.getvalue())
        except Exception as e:
            print(f"❌ 写入缓存文件 {cache_path} 失败: {e}")

    thumb_data.seek(0) # 重置 BytesIO 对象的指针到开头，以便调用者读取
    return thumb_data, thumb_mime

def get_user_setting(user_id, setting_type, default_value=None):
    """获取用户配置"""
    if not user_id:
        return default_value
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute(
        'SELECT setting_data FROM user_settings WHERE user_id = ? AND setting_type = ?',
        (user_id, setting_type)
    )
    
    result = cursor.fetchone()
    cursor.close()
    
    if result:
        return json.loads(result['setting_data'])
    else:
        # 如果没有找到，初始化默认值
        if default_value is not None:
            set_user_setting(user_id, setting_type, default_value)
        return default_value

def set_user_setting(user_id, setting_type, setting_data):
    """设置用户配置"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        '''INSERT OR REPLACE INTO user_settings 
           (user_id, setting_type, setting_data) VALUES (?, ?, ?)''',
        (user_id, setting_type, json.dumps(setting_data, ensure_ascii=False))
    )
    
    db.commit()
    cursor.close()

def serve_html(html_path, **context):
    """增强版的 HTML 服务函数，支持模板变量"""
    html_directory = os.path.join(root, 'web_app')
    html_file_path = os.path.join(html_directory, html_path)
    
    if os.path.exists(html_file_path):
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 使用 Flask 的 render_template_string 正确渲染模板
        rendered_content = render_template_string(html_content, **context)
        response = make_response(rendered_content)
    else:
        abort(404)
    
    # 设置无缓存头
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

# ---------------- 登录保护装饰器 ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- 登录页 ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_id = loogin_check(username, password)
        print(user_id)
        if user_id:
            session['logged_in'] = True
            session['user_id'] = user_id
            return redirect(url_for('serve_root'))
        # 登录失败，返回带错误信息的页面
        return serve_html('frontend/templates/login.html', error="用户名或密码错误")
    
    # GET 请求
    return serve_html('frontend/templates/login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def serve_root():
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(root, 'data', 'icon', 'app'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

from src.core.DictManage import DataAPI
@app.route('/get_init', methods=['GET'])
@login_required
def get_init():
    user_id = session.get('user_id')
    db_list = get_user_setting(user_id, 'database_list')
    if db_list is None:
        db_list = config.get('DictManage', 'tagbase_list', fallback='').split('|')
        set_user_setting(user_id, 'database_list', db_list)
    db_path = get_user_setting(user_id, 'database_path')
    if db_path is None:
        db_path = db_list[0]
        set_user_setting(user_id, 'database_path', db_path)
    if db_path not in tagbase_data_dict:
        db_path_full = db_path + '.db'
        tagbase_data_dict[db_path] = DataAPI(db_path_full)
    return jsonify({
        'database_list': db_list,
        'database_path': db_path,
    })

@app.route('/switch_db', methods=['POST'])
@login_required
def switch_db():
    db_path = request.json.get('db_path')
    if not db_path:
        return jsonify({'success': False, 'message': '数据库路径不能为空'}), 400
    set_user_setting(session.get('user_id'), 'database_path', db_path)
    if db_path not in tagbase_data_dict:
        db_path_full = db_path + '.db'
        tagbase_data_dict[db_path] = DataAPI(db_path_full)
    return jsonify({'success': True, 'message': f'切换到数据库 {db_path}'})

@app.route('/get_category', methods=['GET'])
@login_required
def get_category():
    db_path = get_user_setting(session.get('user_id'), 'database_path')
    data_api: DataAPI = tagbase_data_dict[db_path]
    results = data_api.query_category()
    
    categories = {}
    category_order = []

    for item in results:
        category_name = item[0]
        tags = data_api.query('category', category_name, 'tag')
        data = {
            "tags": tags,
            "is_special": item[2]
        }
        categories[category_name] = data
        category_order.append(category_name)
    return jsonify({
        'categories': categories,
        'category_order': category_order 
    })

@app.route('/get_special_tags_status', methods=['GET'])
@login_required
def get_special_tags_status():
    # 假设 current_user.id 可以获取当前用户ID
    user_id = session.get('user_id')
    data_api: DataAPI = tagbase_data_dict[get_user_setting(user_id, 'database_path')]
    # 从数据库读取，如果没有就使用默认值初始化
    results = data_api.get_all_special_tags_status()
    default_tags = {item[0]: item[1] for item in results}
    tags_status = get_user_setting(user_id, 'special_tags', default_tags)
    return jsonify(tags_status)

@app.route('/get_category_tree_status', methods=['GET'])
@login_required
def get_category_tree_status():
    user_id = session.get('user_id')
    data_api: DataAPI = tagbase_data_dict[get_user_setting(user_id, 'database_path')]
    # 从数据库读取，如果没有就使用默认值初始化
    categories = data_api.query_category()
    default_categories = {item[0]: True for item in categories}
    category_status = get_user_setting(user_id, 'category_tree', default_categories)
    return jsonify(category_status)

@app.route('/update_special_tags_status', methods=['POST'])
@login_required
def update_special_tags_status():
    """更新用户的特殊标签状态"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "用户未登录"}), 401
        
        # 获取前端发送的JSON数据
        new_status = request.get_json()
        
        if not new_status or not isinstance(new_status, dict):
            return jsonify({"success": False, "message": "无效的数据格式"}), 400
        
        # 保存到数据库
        set_user_setting(user_id, 'special_tags', new_status)
        
        return jsonify({
            "success": True, 
            "message": "特殊标签状态更新成功",
            "data": new_status
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500
    
@app.route('/update_category_tree_status', methods=['POST'])
@login_required
def update_category_tree_status():
    """更新用户的分类树状态"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "用户未登录"}), 401
        
        # 获取前端发送的JSON数据
        new_status = request.get_json()
        
        if not new_status or not isinstance(new_status, dict):
            return jsonify({"success": False, "message": "无效的数据格式"}), 400
        
        # 保存到数据库
        set_user_setting(user_id, 'category_tree', new_status)
        
        return jsonify({
            "success": True, 
            "message": "分类树状态更新成功",
            "data": new_status
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500

@app.route('/get_ui_settings', methods=['GET'])
@login_required
def get_ui_settings():
    user_id = session.get('user_id')
    # 获取缩略图大小设置
    icon_size = get_user_setting(user_id, 'icon_size', 'medium')
    # 获取排序键设置
    sort_key = get_user_setting(user_id, 'sort_key', 'name')
    # 获取排序顺序设置
    sort_order = get_user_setting(user_id, 'sort_order', 'desc')
    # 获取每页显示数量设置
    page_size = get_user_setting(user_id, 'page_size', 100)
    
    return jsonify({
        'icon_size': icon_size,
        'sort_key': sort_key,
        'sort_order': sort_order,
        'page_size': page_size
    })

@app.route('/update_ui_settings', methods=['POST'])
@login_required
def update_ui_settings():
    user_id = session.get('user_id')
    data = request.json
    
    # 更新缩略图大小设置
    if 'icon_size' in data:
        set_user_setting(user_id, 'icon_size', data['icon_size'])
    
    # 更新排序键设置
    if 'sort_key' in data:
        set_user_setting(user_id, 'sort_key', data['sort_key'])
    
    # 更新排序顺序设置
    if 'sort_order' in data:
        set_user_setting(user_id, 'sort_order', data['sort_order'])
    
    # 更新每页显示数量设置
    if 'page_size' in data:
        set_user_setting(user_id, 'page_size', data['page_size'])
    
    return jsonify({'success': True})


import random
from natsort import natsort_keygen
def _sort_files(file_items: list[tuple[str, int, float]], sort_key: str = None, sort_order: str = None):
    """根据当前排序设置对文件路径列表进行排序"""
    if sort_key == "name":
        # 自然排序
        nkey = natsort_keygen(key=lambda item: os.path.basename(item[0]))
        file_items.sort(
            key=nkey,
            reverse=(sort_order == "desc")
        )
    elif sort_key == "size":
        file_items.sort(key=lambda item: item[1], reverse=(sort_order == "desc"))
    elif sort_key == "date":
        file_items.sort(key=lambda item: item[2], reverse=(sort_order == "desc"))
    elif sort_key == "random":
        random.shuffle(file_items)

@app.route('/search_files', methods=['POST'])
@login_required
def search_files():
    data = request.json
    tag_expression = data.get('tag_expression', '')
    special_tags_status: dict[str, int] = data.get('special_tags_status', {})
    sort_key = data.get('sort_key', 'name')  # 默认按名称排序
    sort_order = data.get('sort_order', 'desc')  # 默认降序
    page = data.get('page', 1)  # 当前页数，默认为第一页
    page_size = data.get('page_size', 50)  # 每页显示数量，默认为50
    
    if sort_key not in ["name", "size", "date", "random"]:
        return jsonify({"error": f"错误的排序类型：{sort_key}"}), 400
    
    # 验证页码和每页数量参数
    try:
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 1000))  # 限制最大每页数量以防止性能问题
    except (ValueError, TypeError):
        return jsonify({"error": "页码或每页数量参数无效"}), 400
    
    special_tags_status_list = [
        (tag, int(status))
        for tag, status in special_tags_status.items()
    ]
    db_path = get_user_setting(session.get('user_id'), 'database_path')
    file_items = get_tag_files(tag_expression, tagbase_data_dict[db_path], special_tags_status_list)
    if file_items is False:
        return jsonify({"error": f"错误的表达式：{tag_expression}"}), 400
    _sort_files(file_items, sort_key, sort_order)
    
    # 计算总数
    total = len(file_items)
    
    # 计算起始索引
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    
    # 截取当前页的数据
    paginated_file_items = file_items[start_index:end_index]
    file_paths = [item[0] for item in paginated_file_items]
    
    # 返回分页结果
    return jsonify({
        "file_paths": file_paths,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size  # 向上取整计算总页数
        }
    })

@app.route('/get_thumb', methods=['GET'])
@login_required
def get_thumbnails():
    encoded_path = request.args.get('path')
    size_str = request.args.get('size')
    size = int(size_str)
    
    if not encoded_path:
        return Response("Missing 'path' parameter.", status=400)

    try:
        file_path = urllib.parse.unquote(encoded_path)
    except Exception:
        return Response("Invalid URL encoding.", status=400)

    try:
        data_source, mime_type = get_file_thumb(file_path, size)
    except Exception as e:
        print(f"Error generating thumbnail for {file_path}: {e}")
        return Response("Thumbnail generation failed or file not found.", status=404) 

    return send_file(
        data_source,
        mimetype=mime_type,
        as_attachment=False 
    )

@app.route('/open_file', methods=['GET'])
@login_required
def open_file():
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({'error': '缺少文件路径参数'}), 400

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return jsonify({'error': '文件不存在或路径无效'}), 404
    
    db_path = get_user_setting(session.get('user_id'), 'database_path')
    data_api: DataAPI = tagbase_data_dict[db_path]
    tags = data_api.query('file', file_path, 'tag')
    if not tags:
        print(f'访问权限不足：{file_path}')
        return jsonify({'error': '访问权限不足'}), 403

    mime_type, encoding = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream' # 默认二进制流

    try:
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=os.path.basename(file_path)
        )
    except Exception as e:
        print(f"Error sending file: {e}")
        return jsonify({'error': f'无法打开文件: {str(e)}'}), 500



# ————————————————————————————————————————————————————————————————————————启动服务————————————————————————————————————————————————————————

# 日志过滤器
import re
import logging
class RouteFilter(logging.Filter):
    def __init__(self, excluded_routes: list[str], excluded_codes: set[int] = None):
        '''
        过滤werkzeug日志，排除指定路由的日志
        :param excluded_routes: 要排除的路由列表
        :param excluded_codes: 要排除的状态码集合，默认值为{ 200, 206, 304 }
        '''
        super().__init__()
        self.excluded_routes = excluded_routes
        if excluded_codes is None:
            excluded_codes = { 200, 206, 304 }
        self.excluded_codes = excluded_codes
    
        self.pattern = re.compile(r'"[A-Z]+ (?P<path>\S+) HTTP/[\d.]+" (?P<status>\d{3})')
        self.ansi_escape = re.compile(r'\x1b\[[0-9;]*m')

    def extract_path_and_status(self, log_message):
        log_message = self.ansi_escape.sub('', log_message)
        match = self.pattern.search(log_message)
        if match:
            path = match.group('path')      # '/static/file.js'
            status = int(match.group('status'))  # 200
            return path, status
        else:
            raise ValueError("Log message does not match expected format")

    def filter(self, record):
        message = record.getMessage()
        try:
            path, status = self.extract_path_and_status(message)
        except ValueError:
            return True
        # 检查日志消息是否包含要过滤的路由
        if status not in self.excluded_codes:
            return True
        for route in self.excluded_routes:
            if path.startswith(route):
                return False
        return True

# 添加过滤器到werkzeug日志
werkzeug_logger = logging.getLogger('werkzeug')
route_filter = RouteFilter(['/static/', '/open_file?', '/get_thumb?'])
werkzeug_logger.addFilter(route_filter)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10252, threaded=True)