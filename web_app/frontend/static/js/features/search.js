// /src/components/search.js

import { apiSearchFiles } from '../api.js';
import { globalState } from '../state.js';
import { setupVirtualGrid } from './virtualGrid.js';

// 搜索文件
export function searchFiles(pageOrEvent) {
    // 检查参数是否为事件对象，如果是则默认从第一页开始搜索
    let page = 1;
    if (typeof pageOrEvent === 'number') {
        page = pageOrEvent;
    } else if (pageOrEvent && typeof pageOrEvent.preventDefault === 'function') {
        // 这是一个事件对象，阻止默认行为
        pageOrEvent.preventDefault();
    } else if (pageOrEvent === undefined) {
        // 未传入参数，默认为第一页
        page = 1;
    }
    
    const query = document.getElementById('search-input').value;
    if (!query.trim()) {
        showEmptyResults();
        return;
    }
    
    // 显示加载状态
    showLoadingState();
    
    // 调整请求参数以匹配后端接口，包含特殊标签状态和分页参数
    apiSearchFiles({
        tagExpression: query,
        specialTagsStatus: globalState.specialTagsStatus,
        sort_key: globalState.currentSortKey,
        sort_order: globalState.currentSortOrder,
        page: page,
        page_size: globalState.pagination.pageSize,
    })
    .then(response => {
        // 检查响应是否包含分页信息
        if (response.data && response.data.pagination) {
            // 更新分页状态
            globalState.pagination.currentPage = response.data.pagination.page;
            globalState.pagination.totalPages = response.data.pagination.pages;
            globalState.pagination.totalItems = response.data.pagination.total;
            globalState.pagination.pageSize = response.data.pagination.page_size;
            
            // 显示分页结果
            displayResults(response.data.file_paths);
            showPaginationControls();
        } else {
            // 兼容旧格式（直接返回文件路径数组）
            displayResults(response.data);
            globalState.pagination.currentPage = 1;
            globalState.pagination.totalPages = 1;
            globalState.pagination.totalItems = response.data.length;
            hidePaginationControls();
        }
    })
    .catch(error => {
        console.error('Search failed:', error);
        showErrorState();
    });
}

// 显示分页控件
function showPaginationControls() {
    const resultsContainer = document.getElementById('results-container');
    const paginationContainer = document.getElementById('pagination-controls') || createPaginationControls();
    
    // 确保分页控件在结果下方显示
    if (!document.getElementById('pagination-controls')) {
        resultsContainer.parentNode.insertBefore(paginationContainer, resultsContainer.nextSibling);
    }
    
    updatePaginationDisplay();
}

// 隐藏分页控件
function hidePaginationControls() {
    const paginationContainer = document.getElementById('pagination-controls');
    if (paginationContainer) {
        paginationContainer.style.display = 'none';
    }
}

// 创建分页控件
function createPaginationControls() {
    const paginationDiv = document.createElement('div');
    paginationDiv.id = 'pagination-controls';
    paginationDiv.className = 'pagination-wrapper text-center my-3';
    paginationDiv.innerHTML = `
        <nav aria-label="分页导航">
            <ul class="pagination justify-content-center" id="pagination-list">
                <li class="page-item" id="prev-page-li">
                    <a class="page-link" href="#" id="prev-page" aria-label="Previous">
                        <span aria-hidden="true">&laquo;</span>
                    </a>
                </li>
                <li class="page-item disabled"><span class="page-link" id="page-info">第 1 页，共 1 页</span></li>
                <li class="page-item" id="next-page-li">
                    <a class="page-link" href="#" id="next-page" aria-label="Next">
                        <span aria-hidden="true">&raquo;</span>
                    </a>
                </li>
            </ul>
        </nav>
    `;
    
    // 绑定事件
    document.getElementById('prev-page').addEventListener('click', goToPrevPage);
    document.getElementById('next-page').addEventListener('click', goToNextPage);
    
    return paginationDiv;
}

// 更新分页显示
function updatePaginationDisplay() {
    const pageInfo = document.getElementById('page-info');
    const prevPageLi = document.getElementById('prev-page-li');
    const nextPageLi = document.getElementById('next-page-li');
    
    if (pageInfo) {
        pageInfo.textContent = `第 ${globalState.pagination.currentPage} 页，共 ${globalState.pagination.totalPages} 页 (${globalState.pagination.totalItems} 项)`;
    }
    
    // 控制上一页/下一页按钮的禁用状态
    if (prevPageLi) {
        if (globalState.pagination.currentPage <= 1) {
            prevPageLi.classList.add('disabled');
        } else {
            prevPageLi.classList.remove('disabled');
        }
    }
    
    if (nextPageLi) {
        if (globalState.pagination.currentPage >= globalState.pagination.totalPages) {
            nextPageLi.classList.add('disabled');
        } else {
            nextPageLi.classList.remove('disabled');
        }
    }
}

// 上一页
function goToPrevPage(e) {
    e.preventDefault();
    if (globalState.pagination.currentPage > 1) {
        const newPage = globalState.pagination.currentPage - 1;
        searchFiles(newPage);
    }
}

// 下一页
function goToNextPage(e) {
    e.preventDefault();
    if (globalState.pagination.currentPage < globalState.pagination.totalPages) {
        const newPage = globalState.pagination.currentPage + 1;
        searchFiles(newPage);
    }
}

// 跳转到指定页面
export function goToPage(pageNum) {
    if (pageNum >= 1 && pageNum <= globalState.pagination.totalPages) {
        searchFiles(pageNum);
    }
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
    hidePaginationControls();
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