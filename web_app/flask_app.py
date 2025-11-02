from flask import Flask, Response, request, send_file, send_from_directory, jsonify, make_response
import urllib.parse
from flask_cors import CORS
import warnings
import traceback
warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app, 
     supports_credentials=True, 
     origins=[
         "http://tag2file.online",
         "http://192.168.0.102:10252/tag2file",
    ]
)

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from functools import wraps

app.secret_key = 'a_very_secret_key_change_this'  # 用于加密 session cookie

USERS = {
    "admin": "123456",
}

# ---------------- 登录保护装饰器 ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(session)
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
        if username in USERS and password == USERS[username]:
            session['logged_in'] = True
            session['username'] = username
            print(f"User {username} logged in")
            return redirect(url_for('serve_root'))
        return render_template_string(LOGIN_HTML, error="用户名或密码错误")
    return render_template_string(LOGIN_HTML)

# ---------------- 登出 ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 登录页 HTML 模板
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>登录</title>
  <style>
    body {font-family: sans-serif; display:flex; height:100vh; align-items:center; justify-content:center; background:#f2f2f2;}
    .login-box {background:white; padding:30px; border-radius:12px; box-shadow:0 0 12px rgba(0,0,0,0.1);}
    input {display:block; width:200px; margin:10px 0; padding:8px;}
    button {padding:8px 16px;}
    .error {color:red;}
  </style>
</head>
<body>
  <div class="login-box">
    <h3>登录 tag2file</h3>
    {% if error %}<p class="error">{{error}}</p>{% endif %}
    <form method="post">
      <input type="text" name="username" placeholder="用户名" required>
      <input type="password" name="password" placeholder="密码" required>
      <button type="submit">登录</button>
    </form>
  </div>
</body>
</html>
"""

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

from src.DictManage import DictManage
from src.TagClass import get_tag_files
from src.utils import get_cache_path, root
dictManage = DictManage()


from PIL import Image
from io import BytesIO
import os
import mimetypes
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import cv2
from PyQt5.QtWidgets import QFileIconProvider
from PyQt5.QtCore import QFileInfo, QSize, QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QIcon
from PIL import Image
from io import BytesIO
import os

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
            thumb_mime = 'image/png'
            return thumb_data, thumb_mime
        else:
            return None, None

    if mime_type == 'image/gif':
        # --- 特殊处理 GIF 文件 ---
        with Image.open(file_path) as img:
            with open(file_path, 'rb') as f:
                thumb_data = BytesIO(f.read())
            thumb_mime = 'image/gif'
            return thumb_data, thumb_mime
    
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
        if mime_type.startswith('image/'):
            # --- 普通图片处理 ---
            with Image.open(file_path) as img:
                img.thumbnail((size, size))
                if 'icc_profile' in img.info:
                    del img.info['icc_profile']
                img_byte_array = BytesIO()
                img.save(img_byte_array, format='PNG') 
                img_byte_array.seek(0)
                thumb_data = img_byte_array
                thumb_mime = 'image/png'
                
        elif mime_type == 'audio/mpeg':
            # --- MP3 封面处理 (使用 mutagen) ---
            audio = MP3(file_path, ID3=ID3)
            if audio and audio.tags:
                for tag in audio.tags.keys():
                    if tag.startswith('APIC:'):
                        apic = audio.tags[tag]
                        img_byte_array = BytesIO(apic.data)
                        with Image.open(img_byte_array) as img:
                            img.thumbnail((size, size))
                            final_byte_array = BytesIO()
                            img.save(final_byte_array, format='PNG')
                            final_byte_array.seek(0)
                            thumb_data = final_byte_array
                            thumb_mime = 'image/png'
                        break
            
        elif mime_type.startswith('video/') or mime_type == 'video/mp4':
            # --- 视频文件处理 (使用 cv2 提取第一帧) ---
            video = cv2.VideoCapture(file_path)
            if video.isOpened():
                success, frame = video.read()
                video.release()
                
                if success:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    img.thumbnail((size, size))
                    
                    img_byte_array = BytesIO()
                    img.save(img_byte_array, format='PNG')
                    img_byte_array.seek(0)
                    thumb_data = img_byte_array
                    thumb_mime = 'image/png'

        else:
            pil_img = get_file_icon(file_path, size)
            
            if pil_img:
                img_byte_array = BytesIO()
                pil_img.save(img_byte_array, format='PNG') 
                img_byte_array.seek(0)
                
                thumb_data = img_byte_array
                thumb_mime = 'image/png'
                    
    except Exception as e:
        print(f"❌ 生成文件 {file_path} 的缩略图失败: {e}")
        return None, None

    if thumb_data and use_cache:
        try:
            with open(cache_path, 'wb') as f:
                f.write(thumb_data.getvalue())
            # 重置 BytesIO 对象的指针到开头，以便调用者读取
            thumb_data.seek(0)
        except Exception as e:
            print(f"❌ 写入缓存文件 {cache_path} 失败: {e}")

    return thumb_data, thumb_mime

def serve_tag2file_html(html_path):
    response = make_response(send_from_directory(os.path.join(root, 'web_app'), html_path))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/tag2file')
@login_required
def serve_tag2file_web():
    return serve_tag2file_html('tag2file.html')

@app.route('/')
@login_required
def serve_root():
    return serve_tag2file_html('tag2file_frp.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(root, 'data', 'icon', 'app'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/get_category', methods=['GET'])
def get_category():
    categories = dictManage.relation_graph['category']
    
    serializable_categories = {}
    category_order = []

    for category_name, category_info in categories.items():
        serializable_category = {}

        for key, value in category_info.items():
            if isinstance(value, set):
                serializable_category[key] = list(value)
            else:
                serializable_category[key] = value

        serializable_categories[category_name] = serializable_category
        category_order.append(category_name)
    return jsonify({
        'categories': serializable_categories,
        'category_order': category_order 
    })

@app.route('/get_special_categories', methods=['GET'])
def get_special_categories():
    return jsonify(dictManage.special_categories)

@app.route('/get_special_tags_status', methods=['GET'])
def get_special_tags_status():
    print("Session cookie received:", request.cookies)
    print("Session contents:", session)
    return jsonify(dictManage.special_tags_status)

@app.route('/search_files', methods=['POST'])
def search_files():
    data = request.json
    tag_expression = data.get('tag_expression')
    special_tags_status = data.get('special_tags_status')
    file_paths = get_tag_files(tag_expression, special_tags_status)
    if file_paths is False:
        return jsonify({"error": f"错误的表达式：{tag_expression}"}), 400

    return jsonify(file_paths)

@app.route('/get_thumb', methods=['GET'])
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
def open_file():
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({'error': '缺少文件路径参数'}), 400

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return jsonify({'error': '文件不存在或路径无效'}), 404
    
    if file_path not in dictManage.relation_graph['file']:
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10252, threaded=True)