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
export function apiSearchFiles({ tagExpression, specialTagsStatus, sort_key, sort_order }) {
  return api.post('/search_files', {
    tag_expression: tagExpression,
    special_tags_status: specialTagsStatus,
    sort_key: sort_key,
    sort_order: sort_order,
  });
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
