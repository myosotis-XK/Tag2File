// js/api.js
import axios from 'https://cdn.jsdelivr.net/npm/axios@1.6.8/dist/esm/axios.js';

/**
 * axios 实例（统一管理）
 */
const api = axios.create({
  timeout: 15000,
});

/**
 * ======================
 * 基础接口
 * ======================
 */

// 初始化：获取数据库列表 & 当前数据库
export function apiGetInit() {
  return api.get('/get_init');
}

// 切换数据库
export function apiSwitchDatabase(dbPath) {
  return api.post('/switch_db', {
    db_path: dbPath,
  });
}

/**
 * 获取用户界面设置
 */
export async function apiGetUISettings() {
    try {
        const response = await axios.get('/get_ui_settings');
        return response.data;
    } catch (error) {
        console.error('获取用户界面设置失败:', error);
        throw error;
    }
}

/**
 * 更新用户界面设置
 */
export async function apiUpdateUISettings(settings) {
    try {
        const response = await axios.post('/update_ui_settings', settings);
        return response.data;
    } catch (error) {
        console.error('更新用户界面设置失败:', error);
        throw error;
    }
}

/**
 * ======================
 * 标签 / 分类
 * ======================
 */

// 获取分类 & 标签
export function apiGetCategories() {
  return api.get('/get_category');
}

// 获取特殊标签状态
export function apiGetSpecialTagsStatus() {
  return api.get('/get_special_tags_status');
}

// 更新特殊标签状态
export function apiUpdateSpecialTagsStatus(status) {
  return api.post('/update_special_tags_status', status);
}

// 获取分类树展开状态
export function apiGetCategoryTreeStatus() {
  return api.get('/get_category_tree_status');
}

// 更新分类树状态
export function apiUpdateCategoryTreeStatus(status) {
  return api.post('/update_category_tree_status', status);
}

/**
 * ======================
 * 搜索
 * ======================
 */

// 搜索文件
export function apiSearchFiles({ tagExpression, specialTagsStatus, sort_key, sort_order, page, page_size }) {
  const requestData = {
    tag_expression: tagExpression,
    special_tags_status: specialTagsStatus,
    sort_key: sort_key,
    sort_order: sort_order,
    page_size: page_size,
  };
  
  // 添加分页参数（如果提供）
  if (page !== undefined) {
    requestData.page = page;
  }
  
  return api.post('/search_files', requestData);
}

/**
 * ======================
 * 文件相关
 * ======================
 */

// 获取缩略图
export function apiGetThumbnail(path, size) {
  return `/get_thumb?path=${encodeURIComponent(path)}&size=${size}`;
}

// 打开文件
export function apiOpenFile(path) {
  return `/open_file?path=${encodeURIComponent(path)}`;
}

// 获取文件夹内容
export function apiGetFolderContents({ folderPath, sort_key, sort_order }) {
  return api.post('/get_folder_contents', {
    folder_path: folderPath,
    sort_key,
    sort_order,
  });
}

/**
 * ======================
 * 音频播放器相关
 * ======================
 */

// 获取音频文件元数据（批量）
export async function apiGetAudioMetadata(filePaths) {
  try {
    const response = await api.post('/api/audio/metadata', {
      file_paths: filePaths
    });
    return response.data;
  } catch (error) {
    console.error('获取音频元数据失败:', error);
    throw error;
  }
}

// 获取歌词文件
export async function apiGetLyric(audioPath) {
  try {
    const response = await api.get('/api/audio/lyric', {
      params: { audio_path: audioPath }
    });
    return response.data;
  } catch (error) {
    console.error('获取歌词失败:', error);
    throw error;
  }
}

// 添加或更新音频标记
export async function apiAddOrUpdateMarker(filePath, marker) {
  try {
    const response = await api.post('/api/audio/markers', {
      file_path: filePath,
      marker: marker
    });
    return response.data;
  } catch (error) {
    console.error('添加/更新标记失败:', error);
    throw error;
  }
}

// 删除音频标记
export async function apiDeleteMarker(filePath, markerId) {
  try {
    const response = await api.delete(`/api/audio/markers/${markerId}`, {
      params: { file_path: filePath }
    });
    return response.data;
  } catch (error) {
    console.error('删除标记失败:', error);
    throw error;
  }
}

// 获取标记预设
export async function apiGetMarkerPresets() {
  try {
    const response = await api.get('/api/audio/marker_presets');
    return response.data;
  } catch (error) {
    console.error('获取标记预设失败:', error);
    throw error;
  }
}
