from flask import Flask, Response, request, send_file, send_from_directory, jsonify, make_response
import urllib.parse
from flask_cors import CORS
import warnings
import traceback
warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app)  # 🔥 允许所有前端访问（包括 file://）

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
from PyQt5.QtWidgets import QFileIconProvider, QApplication
from PyQt5.QtCore import QFileInfo, QSize, QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QIcon, QPixmap
from PIL import Image
from io import BytesIO
import sys
import os

# 初始化 QApplication
# 必须在创建任何 QWidget 或相关对象（如 QFileIconProvider）之前完成
# 使用 try-except 来避免重复创建 QApplication 实例（在某些环境中可能不需要）
if not QApplication.instance():
    qt_app = QApplication(sys.argv)
else:
    qt_app = QApplication.instance()

# 创建一个全局的 QIconProvider 实例，因为它创建起来可能比较耗时
# 并且 QIconProvider.icon() 方法通常是线程安全的（如果只用于读取图标）
_icon_provider = QFileIconProvider()


def qicon_to_pil_image(qicon: QIcon, size: int) -> Image.Image | None:
    """
    将 QIcon 转换为指定大小的 PIL Image 对象。
    """
    # 尝试获取指定大小的 QPixmap
    qsize = QSize(size, size)
    pixmap = qicon.pixmap(qsize)

    if pixmap.isNull():
        # 如果指定大小没有有效的 pixmap，尝试获取最大可用尺寸并缩放
        # 或者直接返回 None
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
        # 如果文件不存在，QFileInfo 仍能工作并根据扩展名提供图标（在某些系统上）
        # 但最好还是检查一下，或者根据需求决定是否处理不存在的文件。
        # 对于不存在的文件，QFileIconProvider 可能会返回通用文件图标。
        pass

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
        # 文件不存在，无法生成或查找缓存
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
            # 统一将系统图标保存为 PNG 格式
            pil_img.save(img_byte_array, format='PNG') 
            img_byte_array.seek(0)
            
            thumb_data = img_byte_array
            thumb_mime = 'image/png'
            return thumb_data, thumb_mime
        else:
            # 如果无法获取系统图标，返回默认的文件图标
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
            # 继续尝试重新生成

    # 2. 生成缩略图
    try:
        if mime_type.startswith('image/'):
            # --- 普通图片处理 ---
            with Image.open(file_path) as img:
                img.thumbnail((size, size))
                if 'icc_profile' in img.info:
                    del img.info['icc_profile']
                img_byte_array = BytesIO()
                # 统一将缩略图保存为 PNG 格式
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
                            img.save(final_byte_array, format='PNG') # 统一保存为 PNG
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
                    # 视频帧使用 JPEG 编码，然后保存为 PNG
                    img.save(img_byte_array, format='PNG')
                    img_byte_array.seek(0)
                    thumb_data = img_byte_array
                    thumb_mime = 'image/png'

        else:
            # 尝试获取系统图标
            pil_img = get_file_icon(file_path, size)
            
            if pil_img:
                img_byte_array = BytesIO()
                # 统一将系统图标保存为 PNG 格式
                pil_img.save(img_byte_array, format='PNG') 
                img_byte_array.seek(0)
                
                thumb_data = img_byte_array
                thumb_mime = 'image/png'
                    
    except Exception as e:
        print(f"❌ 生成文件 {file_path} 的缩略图失败: {e}")
        return None, None # 生成失败

    
    # 3. 写入磁盘缓存
    if thumb_data and use_cache:
        try:
            # 将 BytesIO 对象的内容写入文件
            with open(cache_path, 'wb') as f:
                f.write(thumb_data.getvalue())
            # 重置 BytesIO 对象的指针到开头，以便调用者读取
            thumb_data.seek(0)
        except Exception as e:
            print(f"❌ 写入缓存文件 {cache_path} 失败: {e}")
            # 即使写入失败，我们仍然返回已生成的缩略图数据

    return thumb_data, thumb_mime

WEB_APP_DIR = os.path.join(root, 'web_app')
@app.route('/tag2file')
def serve_tag2file_web():
    response = make_response(send_from_directory(WEB_APP_DIR, 'tag2file.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(WEB_APP_DIR, 'icon'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/get_category', methods=['GET'])
def get_category():
    # 获取原始的 category 数据
    categories = dictManage.relation_graph['category']
    
    # 创建一个新的字典，用于存储转换后的数据
    serializable_categories = {}
    category_order = []
    # 遍历每个类别
    for category_name, category_info in categories.items():
        # 创建一个新的字典来存储该类别的信息
        serializable_category = {}
        
        # 遍历该类别的所有属性
        for key, value in category_info.items():
            # 如果属性值是 set 类型，转换为 list
            if isinstance(value, set):
                serializable_category[key] = list(value)
            else:
                serializable_category[key] = value
        
        # 添加到结果字典中
        serializable_categories[category_name] = serializable_category
        category_order.append(category_name)

    return jsonify({
        'categories': serializable_categories,
        'category_order': category_order 
    })

@app.route('/get_special_categories', methods=['GET'])
def get_special_categories():
    return jsonify(dictManage.special_categories) # 特殊标签列表

@app.route('/get_special_tags_status', methods=['GET'])
def get_special_tags_status():
    return jsonify(dictManage.special_tags_status) # 特殊标签状态列表

@app.route('/search_files', methods=['POST'])
def search_files():
    data = request.json
    tag_expression = data.get('tag_expression')
    special_tags_status = data.get('special_tags_status')
    file_paths = get_tag_files(tag_expression, special_tags_status)
    if file_paths is False:
        return jsonify({"error": f"错误的表达式：{tag_expression}"}), 400

    return jsonify(file_paths) # 文件路径列表

@app.route('/get_thumb', methods=['GET'])
def get_thumbnails():
    encoded_path = request.args.get('path')
    size_str = request.args.get('size')
    size = int(size_str)
    
    if not encoded_path:
        return Response("Missing 'path' parameter.", status=400)
    
    # URL解码以获取真实路径 (如 C:\Users\file.jpg)
    try:
        file_path = urllib.parse.unquote(encoded_path)
    except Exception:
        return Response("Invalid URL encoding.", status=400)

    # 2. 调用缩略图生成函数
    try:
        data_source, mime_type = get_file_thumb(file_path, size)
    except Exception as e:
        # 实际项目中应记录错误日志
        print(f"Error generating thumbnail for {file_path}: {e}")
        # 如果文件不存在，或者处理失败，返回 404
        return Response("Thumbnail generation failed or file not found.", status=404) 

    # 3. 发送文件流给前端
    # send_file 会自动处理响应头，如 Content-Type
    return send_file(
        data_source,
        mimetype=mime_type,
        # 如果 data_source 是 BytesIO 对象，需要指定 as_attachment=False
        as_attachment=False 
    )

@app.route('/open_file', methods=['GET'])
def open_file():
    # 1. 获取并解码文件路径
    # 前端通过 encodeURIComponent 编码，后端需要解码
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({'error': '缺少文件路径参数'}), 400

    # URL解码，处理路径中的特殊字符
    # file_path = unquote(file_path_encoded)
    
    # 替换前端可能带来的 /，确保在 Windows 上路径分隔符正确
    # 注意：Flask的send_file在Windows上通常能处理正斜杠，但为安全和兼容性，最好确保路径是操作系统原生格式。
    # 在Windows上，以下这步通常不是必须的，但可以增加兼容性
    # file_path = file_path.replace('/', os.sep) 

    # 2. 安全检查
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return jsonify({'error': '文件不存在或路径无效'}), 404
        
    # **关键安全检查：限制文件访问范围**
    # ⚠️ 强烈建议添加逻辑确保 file_path 不会超出应用配置的根目录。
    # 否则，恶意用户可以通过 ../ 访问服务器上的任何文件。
    # 示例 (需要您配置一个根目录): 
    # ROOT_DIR = "D:\\MyFileLibrary\\"
    # if not file_path.startswith(ROOT_DIR):
    #     return jsonify({'error': '访问权限不足'}), 403


    # 3. 推断 MIME Type 并准备发送
    # 推断文件的MIME类型，以便浏览器正确处理（如图片直接显示，文档提示下载）
    mime_type, encoding = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream' # 默认二进制流

    try:
        # Flask的 send_file 函数负责高效地发送文件
        # as_attachment=False：浏览器尝试在页面内显示文件（如图片、PDF）
        # download_name：设置下载时的文件名
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
    # print(dictManage.relation_graph['category'])