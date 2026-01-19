// /src/components/search.js

import { apiSearchFiles } from '../api.js';
import { globalState } from '../state.js';
import { setupVirtualGrid } from './virtualGrid.js';

// 搜索文件
export function searchFiles() {
    const query = document.getElementById('search-input').value;
    if (!query.trim()) {
        showEmptyResults();
        return;
    }
    
    // 显示加载状态
    showLoadingState();
    
    // 修改：调整请求参数以匹配后端接口，包含特殊标签状态
    apiSearchFiles({
        tagExpression: query,
        specialTagsStatus: globalState.specialTagsStatus,
        sort_key: globalState.currentSortKey,
        sort_order: globalState.currentSortOrder
    })
    .then(response => {
        displayResults(response.data);
    })
    .catch(error => {
        console.error('Search failed:', error);
        showErrorState();
    });
}

// 清空搜索输入
export function clearSearch() {
    const searchInput = document.getElementById('search-input');
    searchInput.value = '';
    expressionBuilder.clear();
    
    // 移除所有标签的激活状态
    const activeTags = document.querySelectorAll('.tag-item.active');
    activeTags.forEach(tag => {
        tag.classList.remove('active');
    });
    
    // 重置结果显示
    showEmptyResults();
}

// 显示加载状态
function showLoadingState() {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>搜索中...</p>
        </div>
    `;
}

// 显示错误状态
function showErrorState() {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = `
        <div class="text-center text-danger py-5">
            <i class="fa fa-exclamation-circle fa-3x mb-3"></i>
            <p>搜索失败，请检查服务器连接</p>
        </div>
    `;
}

// 显示空结果状态
function showEmptyResults() {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = `
        <div class="text-center text-muted py-5">
            <i class="fa fa-search fa-3x mb-3"></i>
            <p>请输入集合表达式进行搜索</p>
        </div>
    `;
    // 清空全局文件列表
    globalState.virtualFiles = [];
}

function displayResults(filePaths) {
    // 1. 转换并缓存文件数据
    globalState.virtualFiles = filePaths.map(filePath => {
        const fileName = filePath.split('\\').pop().split('/').pop();
        return { 
            filePath, 
            fileName
        };
    });
    
    // 2. 设置和渲染网格
    globalState.renderedIndexes = new Set(); // 重置索引
    setupVirtualGrid();
}