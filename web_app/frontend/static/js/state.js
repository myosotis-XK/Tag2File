export const globalState = {
    specialTagsStatus: {}, // 特殊标签的启用状态
    categoryTreeStatus: {}, // 分类树的展开状态
    currentSortKey: 'name', // 排序键: name, size, date, random
    currentSortOrder: 'desc', // 排序顺序: asc, desc    
    currentIconSize: 'medium', // small, medium, large
    sizeMap: { small: 56, medium: 85, large: 170 }, // 尺寸映射表
    currentDatabasePath: '', // 当前选中的数据库路径
    availableDatabases: [], // 存储所有可用的数据库 *完整路径*列表
    renderedIndexes: new Set(), // 已渲染的文件索引集合
    virtualFiles: [], // 缓存所有文件信息
    pagination: { // 分页状态
        currentPage: 1,
        totalPages: 1,
        totalItems: 0,
        pageSize: 100, // 每页显示数量
    },
    browseMode: 'search',
    searchSnapshot: null,
    browseRoot: null,
    currentFolder: null,
    pendingScrollTop: null,
};

const MAIN_VIEW_STATE_KEY = 'tag2file.mainView.state';

export function buildVirtualFile(filePath, extra = {}) {
    const normalizedPath = filePath.replace(/\\/g, '/');
    const fileName = normalizedPath.split('/').pop() || normalizedPath;
    return {
        filePath: normalizedPath,
        fileName,
        isDirectory: false,
        fileSize: 0,
        fileDate: 0,
        ...extra,
    };
}

export function clearBrowseState() {
    globalState.browseMode = 'search';
    globalState.searchSnapshot = null;
    globalState.browseRoot = null;
    globalState.currentFolder = null;
    globalState.pendingScrollTop = null;
}

function normalizeStoredVirtualFiles(files) {
    if (!Array.isArray(files)) {
        return [];
    }
    return files
        .filter(file => file && typeof file.filePath === 'string')
        .map(file => buildVirtualFile(file.filePath, {
            fileName: typeof file.fileName === 'string' ? file.fileName : undefined,
            isDirectory: file.isDirectory === true,
            fileSize: Number.isFinite(file.fileSize) ? file.fileSize : 0,
            fileDate: Number.isFinite(file.fileDate) ? file.fileDate : 0,
        }));
}

export function saveMainViewState(state) {
    try {
        sessionStorage.setItem(MAIN_VIEW_STATE_KEY, JSON.stringify(state));
        return true;
    } catch (error) {
        console.warn('保存主界面状态失败:', error);
        return false;
    }
}

export function loadMainViewState() {
    try {
        const raw = sessionStorage.getItem(MAIN_VIEW_STATE_KEY);
        if (!raw) {
            return null;
        }
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') {
            return null;
        }
        return {
            query: typeof parsed.query === 'string' ? parsed.query : '',
            browseMode: parsed.browseMode === 'folder_browse' ? 'folder_browse' : 'search',
            browseRoot: typeof parsed.browseRoot === 'string' ? parsed.browseRoot : null,
            currentFolder: typeof parsed.currentFolder === 'string' ? parsed.currentFolder : null,
            currentDatabasePath: typeof parsed.currentDatabasePath === 'string' ? parsed.currentDatabasePath : '',
            pendingScrollTop: Number.isFinite(parsed.pendingScrollTop) ? parsed.pendingScrollTop : 0,
            pagination: parsed.pagination && typeof parsed.pagination === 'object'
                ? {
                    currentPage: Number.isFinite(parsed.pagination.currentPage) ? parsed.pagination.currentPage : 1,
                    totalPages: Number.isFinite(parsed.pagination.totalPages) ? parsed.pagination.totalPages : 1,
                    totalItems: Number.isFinite(parsed.pagination.totalItems) ? parsed.pagination.totalItems : 0,
                    pageSize: Number.isFinite(parsed.pagination.pageSize) ? parsed.pagination.pageSize : 100,
                }
                : { currentPage: 1, totalPages: 1, totalItems: 0, pageSize: 100 },
            virtualFiles: normalizeStoredVirtualFiles(parsed.virtualFiles),
            searchSnapshot: parsed.searchSnapshot && typeof parsed.searchSnapshot === 'object'
                ? {
                    query: typeof parsed.searchSnapshot.query === 'string' ? parsed.searchSnapshot.query : '',
                    pagination: parsed.searchSnapshot.pagination && typeof parsed.searchSnapshot.pagination === 'object'
                        ? {
                            currentPage: Number.isFinite(parsed.searchSnapshot.pagination.currentPage) ? parsed.searchSnapshot.pagination.currentPage : 1,
                            totalPages: Number.isFinite(parsed.searchSnapshot.pagination.totalPages) ? parsed.searchSnapshot.pagination.totalPages : 1,
                            totalItems: Number.isFinite(parsed.searchSnapshot.pagination.totalItems) ? parsed.searchSnapshot.pagination.totalItems : 0,
                            pageSize: Number.isFinite(parsed.searchSnapshot.pagination.pageSize) ? parsed.searchSnapshot.pagination.pageSize : 100,
                        }
                        : { currentPage: 1, totalPages: 1, totalItems: 0, pageSize: 100 },
                    scrollTop: Number.isFinite(parsed.searchSnapshot.scrollTop) ? parsed.searchSnapshot.scrollTop : 0,
                    virtualFiles: normalizeStoredVirtualFiles(parsed.searchSnapshot.virtualFiles),
                }
                : null,
        };
    } catch (error) {
        console.warn('读取主界面状态失败:', error);
        return null;
    }
}

export function clearMainViewState() {
    sessionStorage.removeItem(MAIN_VIEW_STATE_KEY);
}

import { apiGetUISettings, apiUpdateUISettings } from './api.js';
// 初始化状态函数
export async function initializeState() {
    try {
        // 从后端获取用户界面设置
        const settings = await apiGetUISettings();
        
        // 更新状态
        if (settings.icon_size) {
            globalState.currentIconSize = settings.icon_size;
        }
        
        if (settings.sort_key) {
            globalState.currentSortKey = settings.sort_key;
        }
        
        if (settings.sort_order) {
            globalState.currentSortOrder = settings.sort_order;
        }

        if (settings.page_size) {
            globalState.pagination.pageSize = settings.page_size;
        }
    } catch (error) {
        console.error('加载用户界面设置失败，使用默认值:', error);
        // 使用默认值继续
    }
}

// 保存用户界面设置到后端
export async function saveUISettings() {
    try {
        const settings = {
            icon_size: globalState.currentIconSize,
            sort_key: globalState.currentSortKey,
            sort_order: globalState.currentSortOrder,
            page_size: globalState.pagination.pageSize,
        };
        
        await apiUpdateUISettings(settings);
    } catch (error) {
        console.error('保存用户界面设置失败:', error);
    }
}
