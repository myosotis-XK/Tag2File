import { globalState } from '../state.js';
import {
    apiGetCategories,
    apiGetSpecialTagsStatus,
    apiGetCategoryTreeStatus,
    apiUpdateSpecialTagsStatus,
    apiUpdateCategoryTreeStatus
} from '../api.js';

import { searchFiles } from './search.js';
import { insertAtCursor, FILE_TYPE_ICON_MAP } from '../utils.js';

// tagExpression.js
export class TagExpressionBuilder {
    constructor() {
        this.expression = '';
    }

    addTag(tag) {
        if (this.expression) {
            this.expression += ' & ' + tag;
        } else {
            this.expression = tag;
        }
        return this;
    }

    clear() {
        this.expression = '';
        return this;
    }

    toString() {
        return this.expression;
    }
}

// 创建全局实例
export const expressionBuilder = new TagExpressionBuilder();

export function loadAvailableTags() {
    Promise.all([
        apiGetCategories(),
        apiGetSpecialTagsStatus(),
        apiGetCategoryTreeStatus()
    ])
    .then(([categoryResponse, specialTagsResponse, categoryTreeResponse]) => {
        const tagTreeContainer = document.getElementById('tag-tree');
        tagTreeContainer.innerHTML = '';
        
        const categories = categoryResponse.data.categories;
        const categoryOrder = categoryResponse.data.category_order;

        globalState.specialTagsStatus = specialTagsResponse.data || {};
        globalState.categoryTreeStatus = categoryTreeResponse.data  || {};

        for (const category of categoryOrder) {
            const category_info = categories[category];
            // 1. 创建类别标题容器，添加折叠图标和点击样式
            const categoryHeaderContainer = document.createElement('div');
            categoryHeaderContainer.className = 'category-header d-flex justify-content-between align-items-center'; // 使用 d-flex 布局
            categoryHeaderContainer.style.cursor = 'pointer'; // 添加手型光标

            const categoryText = document.createElement('span');
            categoryText.textContent = category;
            categoryHeaderContainer.appendChild(categoryText);

            // 折叠图标 - 根据保存的状态设置初始状态
            const collapseIcon = document.createElement('i');
            const isCategoryCollapsed = globalState.categoryTreeStatus[category] === false;
            collapseIcon.className = isCategoryCollapsed ? 'fa fa-caret-right' : 'fa fa-caret-down';
            categoryHeaderContainer.appendChild(collapseIcon);

            tagTreeContainer.appendChild(categoryHeaderContainer);
            
            // 2. 创建标签列表容器 (可折叠部分)
            const tagListContainer = document.createElement('div');
            tagListContainer.className = 'tag-list-body';
            tagListContainer.style.display = isCategoryCollapsed ? 'none' : 'block';
            
            // 获取该类别的标签
            const tags = category_info.tags;
            const categoryTags = tags ? Array.from(tags) : [];
            
            // 3. 为类别标题添加折叠事件
            categoryHeaderContainer.addEventListener('click', () => {
                // 切换显示状态
                const isCollapsed = tagListContainer.style.display === 'none';
                if (isCollapsed) {
                    tagListContainer.style.display = 'block';
                    collapseIcon.className = 'fa fa-caret-down'; // 展开时向下箭头
                    globalState.categoryTreeStatus[category] = true
                } else {
                    tagListContainer.style.display = 'none';
                    collapseIcon.className = 'fa fa-caret-right'; // 折叠时向右箭头
                    globalState.categoryTreeStatus[category] = false
                }

                updateCategoryTreeStatusToBackend();
            });

            // 4. 将标签项添加到新的 tagListContainer 中
            categoryTags.forEach(tag => {
                const tagItem = document.createElement('div');
                
                if (category_info.is_special) {
                    // 特殊类别标签
                    tagItem.className = 'tag-item special-tag';
                    const isChecked = globalState.specialTagsStatus[tag] !== false;
                    if (isChecked) {
                        tagItem.classList.add('checked');
                    }
                    
                    let iconHtml = '';
                    if (category === '文件类型' && FILE_TYPE_ICON_MAP[tag]) {
                        iconHtml = `<i class="fa ${FILE_TYPE_ICON_MAP[tag]} me-2"></i>`;
                    }
                    
                    tagItem.innerHTML = `
                        <span class="check-box">${isChecked ? '✓' : ''}</span>
                        <span class="tag-text">${iconHtml}${tag}</span>
                    `;
                    
                    tagItem.addEventListener('click', (e) => {
                        e.stopPropagation();
                        
                        const isCurrentlyChecked = tagItem.classList.contains('checked');
                        if (isCurrentlyChecked) {
                            tagItem.classList.remove('checked');
                            tagItem.querySelector('.check-box').textContent = '';
                            globalState.specialTagsStatus[tag] = false;
                        } else {
                            tagItem.classList.add('checked');
                            tagItem.querySelector('.check-box').textContent = '✓';
                            globalState.specialTagsStatus[tag] = true;
                        }
                        
                        updateSpecialTagsStatusToBackend();
                        
                        const currentQuery = document.getElementById('search-input').value;
                        if (currentQuery.trim()) {
                            searchFiles();
                        }
                    });
                } else {
                    // 普通标签
                    tagItem.className = 'tag-item';
                    tagItem.textContent = tag;
                    
                    tagItem.addEventListener('click', () => {
                        const searchInput = document.getElementById('search-input');
                        insertAtCursor(searchInput, tag);
                    });
                }
                
                // 将标签添加到列表容器
                tagListContainer.appendChild(tagItem); 
            });
            
            // 5. 将标签列表容器添加到总容器中
            tagTreeContainer.appendChild(tagListContainer);
        }

    })
    .catch(error => {
        console.error('Failed to load tags:', error);
        const tagTreeContainer = document.getElementById('tag-tree');
        tagTreeContainer.innerHTML = `
            <div class="text-center text-danger py-4">
                <i class="fa fa-exclamation-circle fa-2x mb-2"></i>
                <p>加载标签库失败，请检查服务器连接</p>
            </div>
        `;
    });
}

function updateSpecialTagsStatusToBackend() {
    apiUpdateSpecialTagsStatus(globalState.specialTagsStatus)
    .then(response => {
        if (!response.data.success) {
            console.error('保存特殊标签状态失败:', response.data.message);
        }
    })
    .catch(error => {
        console.error('保存特殊标签状态失败:', error);
    });
}

function updateCategoryTreeStatusToBackend() {
    apiUpdateCategoryTreeStatus(globalState.categoryTreeStatus)
    .then(response => {
        if (!response.data.success) {
            console.error('保存分类树状态失败:', response.data.message);
        }
    })
    .catch(error => {
        console.error('保存分类树状态失败:', error);
    });
}