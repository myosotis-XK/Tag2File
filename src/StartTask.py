from .utils import *
import os
import shutil
import time
import configparser

def start_task():
    manage_cache_process()
    return True

def manage_cache_process(max_age_days=30):
    """完整的缓存管理进程，包括检查条件和清理"""
    cache_config = configparser.ConfigParser()
    config_path = os.path.join(root, 'config', 'cache_config.ini')
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