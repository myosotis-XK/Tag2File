from .utils import *
import os
import shutil
import time
import configparser

def start_task():
    manage_cache_process()
    backup_tagbase()
    return True


def backup_tagbase():
    """三级标签库备份：当前启动（一级）、上次启动（二级）、一天前启动（三级）"""
    # 获取标签库路径
    floder_path = config.get('DictManage', 'tagbase_path', fallback='default_folder')
    if floder_path == 'default_folder':
        floder_path = os.path.join(root, 'data', 'tag')
    tagbase_name = config.get('DictManage', 'tagbase_name', fallback='tagbase')
    tagbase_path = os.path.join(floder_path, tagbase_name)
    
    # 备份目录（标签库目录下的 backup 子目录）
    backup_dir = os.path.join(floder_path, "backup")
    os.makedirs(backup_dir, exist_ok=True)  # 创建备份目录（若不存在）
    
    # 定义三级备份文件名（不带扩展名）
    current_backup = os.path.join(backup_dir, f"{tagbase_name}_current")   # 一级：当前启动备份
    previous_backup = os.path.join(backup_dir, f"{tagbase_name}_previous") # 二级：上次启动备份
    one_day_ago_backup = os.path.join(backup_dir, f"{tagbase_name}_one_day_ago") # 三级：一天前备份    

    # 工具函数：处理带扩展名的文件（shelve 会生成 .dir/.dat/.bak 等）
    def process_files(src_prefix, dest_prefix, action="copy"):
        for ext in ["", ".dir", ".dat", ".bak"]:  # 匹配所有关联文件
            src = f"{src_prefix}{ext}"
            dest = f"{dest_prefix}{ext}"
            if os.path.exists(src):
                if action == "copy":
                    shutil.copy2(src, dest)  # 复制并保留元数据
                elif action == "rename":
                    if os.path.exists(dest):
                        os.remove(dest)
                    os.rename(src, dest)
                elif action == "delete":
                    os.remove(src)

    # 1. 二级备份升级为三级备份（仅当二级备份创建时间超过24小时）
    previous_backup_dir = f"{previous_backup}.dir"  # 选择 .dir 文件作为时间参考
    if os.path.exists(previous_backup_dir):
        prev_create_time = os.path.getctime(previous_backup_dir)  # 获取创建时间（Windows为文件创建时间，Unix为元数据修改时间）
        current_time = time.time()
        if current_time - prev_create_time >= 86400:  # 24小时 = 86400秒
            process_files(previous_backup, one_day_ago_backup, "rename")
            print("二级备份已超过24小时，升级为三级备份")
        else:
            print("二级备份未超过24小时，不升级为三级备份")
    
    # 2. 一级备份升级为二级备份（当前 → 上次）
    if os.path.exists(f"{current_backup}.dir"):  # 检查一级备份是否存在
        process_files(current_backup, previous_backup, "rename")
    
    # 3. 复制当前标签库到一级备份（覆盖或新建）
    process_files(tagbase_path, current_backup, "copy")
    print("标签库三级备份完成")


def manage_cache_process(max_age_days=30):
    """完整的缓存管理进程，包括检查条件和清理"""
    cache_config = configparser.ConfigParser()
    config_path = os.path.join(root, 'data', 'cache_config.ini')
    if not os.path.exists(config_path):
        with open(config_path, 'w', encoding='utf-8') as configfile:
            cache_config.write(configfile)
    cache_config.read(config_path, encoding='utf-8')
    
    if not cache_config.has_section('CacheCleaner'):
        cache_config.add_section('CacheCleaner')
    last_clean_time = cache_config.getint('CacheCleaner', 'last_clean_time', fallback=0)
    # 检查条件1: 距离上次清理时间 > max_age_days  
    days_since_last_clean = (time.time() - last_clean_time) / (24 * 60 * 60)  
    should_clean_by_time = days_since_last_clean > max_age_days   

    # 如果满足任一条件，执行清理
    if should_clean_by_time:
        cache_dir = os.path.join(root, 'data', 'cache', 'image')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        clean_cache(cache_dir, max_age_days)
        # 更新配置文件中的上次清理时间
        cache_config.set('CacheCleaner', 'last_clean_time', str(int(time.time())))
        with open(config_path, 'w') as configfile:
            cache_config.write(configfile)
        print("缓存清理完成")
    else:
        print("距离上次清理时间不足，跳过清理")
    return True

def clean_cache(cache_dir, max_age_days=30):
    """清理指定目录中的过期缓存文件"""
    now = time.time()
    expiration_time = now - (max_age_days * 24 * 60 * 60)

    # 遍历所有缓存文件
    for root, dirs, files in os.walk(cache_dir):  
        for file in files:  
            file_path = os.path.join(root, file)  
            # 获取文件的访问时间  
            file_stat = os.stat(file_path)  
            # 使用修改时间或访问时间，取决于您的策略  
            file_time = file_stat.st_atime  # 或 st_mtime(修改时间)
            
            if file_time < expiration_time:  
                os.remove(file_path)
    return True