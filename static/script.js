/**
 * AI 智能助手 - 前端 JavaScript
 * WebSocket 連接與聊天邏輯
 */

// ========== 全域變數 ==========
let ws = null;
let clientId = generateClientId();
let isConnected = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000;

// 當前訊息的 DOM 元素（用於串流更新）
let currentAssistantMessage = null;
let currentMessageContent = '';

// 知識圖譜相關變數
let network = null;
let graphData = null;

// 圖片上傳相關變數
let pendingImages = []; // 存儲待發送的圖片 (Base64 格式)

// ========== 圖片處理邏輯 ==========

/**
 * 處理圖片選擇 (從文件選擇器)
 */
function handleImageSelect(event) {
    const files = event.target.files;
    if (files.length > 0) {
        Array.from(files).forEach(file => {
            if (file.type.startsWith('image/')) {
                addImageToPreview(file);
            }
        });
    }
    // 清空 input 以便重複選擇同一文件
    event.target.value = '';
}

/**
 * 處理 Ctrl+V 貼上圖片
 */
function handlePaste(event) {
    const items = event.clipboardData?.items;
    if (!items) return;

    for (let item of items) {
        if (item.type.startsWith('image/')) {
            event.preventDefault();
            const file = item.getAsFile();
            if (file) {
                addImageToPreview(file);
            }
            break;
        }
    }
}

/**
 * 將圖片添加到預覽區域
 */
function addImageToPreview(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const base64 = e.target.result;
        const imageId = 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

        pendingImages.push({
            id: imageId,
            data: base64,
            name: file.name,
            type: file.type
        });

        const container = document.getElementById('imagePreviewContainer');
        container.classList.add('has-images');

        const previewItem = document.createElement('div');
        previewItem.className = 'image-preview-item';
        previewItem.id = imageId;
        previewItem.innerHTML = `
            <img src="${base64}" alt="${file.name}">
            <button class="remove-btn" onclick="removeImage('${imageId}')" title="移除圖片">×</button>
        `;

        container.appendChild(previewItem);
    };
    reader.readAsDataURL(file);
}

/**
 * 移除預覽中的圖片
 */
function removeImage(imageId) {
    // 從陣列中移除
    pendingImages = pendingImages.filter(img => img.id !== imageId);

    // 從 DOM 中移除
    const element = document.getElementById(imageId);
    if (element) {
        element.remove();
    }

    // 如果沒有圖片了，移除 has-images 類別
    const container = document.getElementById('imagePreviewContainer');
    if (pendingImages.length === 0) {
        container.classList.remove('has-images');
    }
}

/**
 * 清空所有預覽圖片
 */
function clearAllImages() {
    pendingImages = [];
    const container = document.getElementById('imagePreviewContainer');
    container.innerHTML = '';
    container.classList.remove('has-images');
}

// ========== PDF 上傳邏輯 ==========

// 已上傳的文件列表
let uploadedDocuments = [];

/**
 * 初始化 PDF 上傳功能
 */
function initPDFUpload() {
    const dropzone = document.getElementById('uploadDropzone');
    const pdfInput = document.getElementById('pdfInput');

    if (!dropzone || !pdfInput) return;

    // 拖放事件
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');

        const files = e.dataTransfer.files;
        handlePDFFiles(files);
    });

    // 點擊上傳區域
    dropzone.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON') {
            pdfInput.click();
        }
    });

    // 文件選擇
    pdfInput.addEventListener('change', (e) => {
        handlePDFFiles(e.target.files);
        e.target.value = ''; // 清空以便重複選擇
    });

    // 載入已上傳的文件列表
    loadUploadedDocuments();
}

/**
 * 從後端載入已上傳的文件列表
 */
async function loadUploadedDocuments() {
    try {
        const response = await fetch('/api/documents');
        if (!response.ok) return;

        const data = await response.json();

        if (data.documents && data.documents.length > 0) {
            // 清空現有列表
            uploadedDocuments = [];

            // 添加每個已存儲的文件
            data.documents.forEach(doc => {
                const docObj = {
                    id: doc.id,
                    name: doc.filename,
                    size: doc.text_length || 0,
                    file: null,  // 已處理的文件沒有原始 file 物件
                    status: 'completed',
                    progress: 100,
                    uploadedAt: new Date(doc.processed_at || Date.now()),
                    extractedData: {
                        entities: doc.entities || [],
                        relations: doc.relations || []
                    }
                };

                uploadedDocuments.push(docObj);
            });

            // 更新 UI
            renderDocumentList();
            console.log(`[Documents] 已載入 ${uploadedDocuments.length} 份已上傳文件`);
        }
    } catch (error) {
        console.log('[Documents] 載入文件列表失敗:', error);
    }
}

/**
 * 重新渲染文件列表 UI
 */
function renderDocumentList() {
    const documentList = document.getElementById('documentList');
    if (!documentList) return;

    // 清空現有內容
    documentList.innerHTML = '';

    if (uploadedDocuments.length === 0) {
        documentList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📁</span>
                <p>尚未上傳任何文件</p>
            </div>
        `;
        return;
    }

    // 渲染每個文件
    uploadedDocuments.forEach(doc => {
        const docElement = createDocumentElement(doc);
        documentList.appendChild(docElement);
    });
}

/**
 * 創建文件元素（統一樣式）
 */
function createDocumentElement(doc) {
    const div = document.createElement('div');
    div.className = 'document-item';
    div.id = `doc-${doc.id}`;

    const statusText = doc.status === 'completed' ? '已完成' :
        doc.status === 'error' ? '處理失敗' :
            doc.status === 'processing' ? '處理中...' : '待處理';

    div.innerHTML = `
        <div class="document-icon">📄</div>
        <div class="document-info">
            <div class="document-name">${escapeHtml(doc.name)}</div>
            <div class="document-meta">${formatFileSize(doc.size)}</div>
        </div>
        <div class="document-status">
            <span class="status-badge ${doc.status}">${statusText}</span>
        </div>
        <div class="document-actions">
            <button class="action-btn delete" onclick="removeDocument('${doc.id}')" title="刪除">🗑️</button>
        </div>
    `;

    return div;
}

/**
 * 處理 PDF 文件
 */
function handlePDFFiles(files) {
    console.log('[PDF] 收到文件:', files.length);
    Array.from(files).forEach(file => {
        console.log('[PDF] 處理文件:', file.name, 'Type:', file.type);
        // 接受 application/pdf 類型或 .pdf 副檔名
        if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
            addDocumentToList(file);
        } else {
            console.warn('[PDF] 非 PDF 文件被忽略:', file.name, 'Type:', file.type);
        }
    });
}

/**
 * 添加文件到列表
 */
function addDocumentToList(file) {
    const docId = 'doc_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    const doc = {
        id: docId,
        name: file.name,
        size: file.size,
        file: file,
        status: 'pending', // pending, processing, completed, error
        progress: 0,
        uploadedAt: new Date()
    };

    uploadedDocuments.push(doc);
    renderDocumentItem(doc);
    updateDocumentStats();
    hideEmptyState();

    // 自動開始上傳處理
    uploadAndProcessDocument(doc);
}

/**
 * 渲染文件項目
 */
function renderDocumentItem(doc) {
    // 直接使用 documentList 作為容器（根據實際 DOM 結構）
    let container = document.getElementById('documentList');

    // 備用選擇器
    if (!container) {
        container = document.getElementById('documentItems');
    }
    if (!container) {
        container = document.querySelector('.document-list');
    }
    if (!container) {
        container = document.querySelector('.document-items');
    }

    if (!container) {
        console.error('[PDF] 找不到文件列表容器');
        return;
    }

    // 隱藏空狀態
    const emptyState = document.getElementById('emptyDocState');
    if (emptyState) emptyState.style.display = 'none';

    const itemHtml = `
        <div class="document-item" id="${doc.id}">
            <div class="document-icon">📄</div>
            <div class="document-info">
                <div class="document-name">${escapeHtml(doc.name)}</div>
                <div class="document-meta">${formatFileSize(doc.size)}</div>
            </div>
            <div class="document-status">
                <span class="status-badge ${doc.status}">${getStatusText(doc.status)}</span>
                <div class="progress-bar" style="display: ${doc.status === 'processing' ? 'block' : 'none'}">
                    <div class="progress-fill" style="width: ${doc.progress}%"></div>
                </div>
            </div>
            <div class="document-actions">
                <button class="action-btn delete" onclick="removeDocument('${doc.id}')" title="刪除">🗑️</button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', itemHtml);
}

/**
 * 更新文件狀態顯示
 * @param {string} docId - 文件 ID
 * @param {string} status - 狀態 (pending/processing/completed/error)
 * @param {number} progress - 進度百分比 (0-100)
 * @param {string} message - 可選的詳細訊息
 */
function updateDocumentStatus(docId, status, progress = 0, message = '') {
    const doc = uploadedDocuments.find(d => d.id === docId);
    if (doc) {
        doc.status = status;
        doc.progress = progress;
    }

    const item = document.getElementById(docId);
    if (!item) return;

    const badge = item.querySelector('.status-badge');
    const progressBar = item.querySelector('.progress-bar');
    const progressFill = item.querySelector('.progress-fill');

    if (badge) {
        badge.className = `status-badge ${status}`;
        // 如果有訊息且狀態是 processing，顯示詳細訊息；否則顯示狀態文字
        if (message && status === 'processing') {
            badge.textContent = message;
        } else {
            badge.textContent = getStatusText(status);
        }
    }

    if (status === 'processing' && progressBar && progressFill) {
        progressBar.style.display = 'block';
        progressFill.style.width = `${progress}%`;
    } else if (progressBar) {
        progressBar.style.display = 'none';
    }
}

/**
 * 上傳並處理文件
 * 注意：實際進度更新由 WebSocket 的 upload_progress 訊息處理
 */
async function uploadAndProcessDocument(doc) {
    // 初始狀態 - 實際進度會由 WebSocket 即時更新
    updateDocumentStatus(doc.id, 'processing', 0, '準備上傳...');

    try {
        // 創建 FormData 上傳文件
        const formData = new FormData();
        formData.append('file', doc.file);
        formData.append('document_id', doc.id);

        // 發送到後端 API - 進度會透過 WebSocket 即時推送
        const response = await fetch('/api/upload-pdf', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`上傳失敗: ${response.status}`);
        }

        const result = await response.json();

        // 如果成功提取了知識，添加到圖譜
        if (result.success && result.entities) {
            addKnowledgeToGraph(
                doc.name,
                result.entities || [],
                result.relations || []
            );
        }

        // HTTP 回應完成時，WebSocket 應該已經發送了 completed 狀態
        // 這裡做最終確認
        if (result.success) {
            updateDocumentStatus(doc.id, 'completed', 100, '處理完成');
        }

        // 更新文檔的提取結果
        const docObj = uploadedDocuments.find(d => d.id === doc.id);
        if (docObj) {
            docObj.extractedData = result;
        }

    } catch (error) {
        console.error('處理文件失敗:', error);
        updateDocumentStatus(doc.id, 'error', 0, error.message);
    }
}

/**
 * 處理上傳進度 WebSocket 訊息
 */
function handleUploadProgress(data) {
    const { doc_id, status, progress, message, total_chunks, current_chunk } = data;

    console.log(`[Upload Progress] 收到進度: ${doc_id}: ${progress}% - ${message}`);

    // 嘗試找到對應的 DOM 元素
    let item = document.getElementById(doc_id);
    console.log(`[Upload Progress] DOM 元素是否存在: ${item ? '是' : '否'}, ID: ${doc_id}`);

    // 如果找不到元素，嘗試在 documentList 容器中創建一個
    if (!item) {
        let container = document.getElementById('documentList');
        if (!container) container = document.getElementById('documentItems');
        if (container) {
            // 隱藏空狀態
            const emptyState = document.getElementById('emptyDocState');
            if (emptyState) emptyState.style.display = 'none';

            // 從 uploadedDocuments 找到文件名（如果有的話）
            const docInfo = uploadedDocuments.find(d => d.id === doc_id);
            const fileName = docInfo ? docInfo.name : '處理中...';
            const fileSize = docInfo ? formatFileSize(docInfo.size) : '';

            // 創建新的進度項目
            const itemHtml = `
                <div class="document-item" id="${doc_id}">
                    <div class="document-icon">📄</div>
                    <div class="document-info">
                        <div class="document-name">${escapeHtml(fileName)}</div>
                        <div class="document-meta">${fileSize}</div>
                    </div>
                    <div class="document-status">
                        <span class="status-badge processing">${message || '處理中'}</span>
                        <div class="progress-bar" style="display: block">
                            <div class="progress-fill" style="width: ${progress}%"></div>
                        </div>
                    </div>
                    <div class="document-actions">
                        <button class="action-btn delete" onclick="removeDocument('${doc_id}')" title="刪除">🗑️</button>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', itemHtml);
            item = document.getElementById(doc_id);
            console.log(`[Upload Progress] 已動態創建 DOM 元素: ${doc_id}`);
        }
    }

    // 更新對應文件的進度顯示
    updateDocumentStatus(doc_id, status, progress, message);

    // 如果有分塊信息，可以顯示更詳細的進度
    if (total_chunks > 0 && current_chunk > 0) {
        updateDocumentChunkInfo(doc_id, current_chunk, total_chunks);
    }
}

/**
 * 更新文件的分塊處理信息
 */
function updateDocumentChunkInfo(docId, currentChunk, totalChunks) {
    const item = document.getElementById(docId);
    if (!item) return;

    // 找到或創建分塊信息顯示元素
    let chunkInfo = item.querySelector('.chunk-info');
    if (!chunkInfo) {
        const statusDiv = item.querySelector('.document-status');
        if (statusDiv) {
            chunkInfo = document.createElement('div');
            chunkInfo.className = 'chunk-info';
            chunkInfo.style.cssText = 'font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;';
            statusDiv.appendChild(chunkInfo);
        }
    }

    if (chunkInfo) {
        chunkInfo.textContent = `區塊 ${currentChunk}/${totalChunks}`;
    }
}




/**
 * 移除文件（同時從 SQLite 刪除）
 */
async function removeDocument(docId) {
    // 從前端列表移除
    uploadedDocuments = uploadedDocuments.filter(d => d.id !== docId);

    const item = document.getElementById(docId) || document.getElementById(`doc-${docId}`);
    if (item) {
        item.remove();
    }

    updateDocumentStats();

    if (uploadedDocuments.length === 0) {
        showEmptyState();
    }

    // 從後端 SQLite 刪除
    try {
        await fetch(`/api/documents/${docId}`, {
            method: 'DELETE'
        });
        console.log(`[Documents] 已從資料庫刪除文件: ${docId}`);
    } catch (error) {
        console.log('[Documents] 刪除文件失敗:', error);
    }
}

/**
 * 更新文件統計
 */
function updateDocumentStats() {
    const totalDocsEl = document.getElementById('totalDocs');
    if (totalDocsEl) {
        totalDocsEl.textContent = uploadedDocuments.length;
    }
}

/**
 * 隱藏空狀態
 */
function hideEmptyState() {
    const emptyState = document.getElementById('emptyDocState');
    if (emptyState) {
        emptyState.style.display = 'none';
    }
}

/**
 * 顯示空狀態
 */
function showEmptyState() {
    const emptyState = document.getElementById('emptyDocState');
    if (emptyState) {
        emptyState.style.display = 'block';
    }
}

/**
 * 獲取狀態文字
 */
function getStatusText(status) {
    const statusMap = {
        pending: '等待中',
        processing: '處理中',
        completed: '已完成',
        error: '錯誤'
    };
    return statusMap[status] || status;
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * 讀取文件為 Base64
 */
function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// ========== UI 互動邏輯 ==========

/**
 * 切換側邊欄收合狀態
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    // 判斷是否為手機版 (螢幕寬度 < 768px)
    if (window.innerWidth <= 768) {
        sidebar.classList.toggle('active');
    } else {
        sidebar.classList.toggle('collapsed');
    }

    // 如果圖譜視圖是活躍的，重新繪製圖譜以適應新寬度
    if (document.getElementById('graphView').classList.contains('active') && network) {
        setTimeout(() => network.redraw(), 300);
    }
}

/**
 * 切換視圖 (對話/知識圖譜)
 */
function switchView(viewName) {
    // 更新導航按鈕狀態
    document.querySelectorAll('.nav-item').forEach(el => {
        if (el.getAttribute('onclick') && el.getAttribute('onclick').includes(viewName)) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }
    });

    // 更新內容區域
    document.querySelectorAll('.view-section').forEach(el => {
        el.classList.remove('active');
    });

    document.getElementById(`${viewName}View`).classList.add('active');

    // 根據視圖類型執行對應操作
    if (viewName === 'graph') {
        // 切換到圖譜時，重新從 SQL 載入最新數據
        loadStoredKnowledge();
    } else if (viewName === 'upload') {
        // 切換到上傳頁面時，重新載入文件列表
        loadUploadedDocuments();
    }
}

/**
 * 切換主題 (深色/亮色)
 */
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';

    html.setAttribute('data-theme', newTheme);

    const icon = document.getElementById('themeIcon');
    icon.textContent = newTheme === 'light' ? '☀️' : '🌙';

    // 儲存偏好
    localStorage.setItem('theme', newTheme);

    // 如果圖譜已初始化，可能需要更新顏色
    if (network) {
        updateGraphTheme(newTheme);
    }
}

/**
 * 初始化主題
 */
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    document.getElementById('themeIcon').textContent = savedTheme === 'light' ? '☀️' : '🌙';
}

/**
 * 設定模態框控制
 */
function toggleSettingsModal() {
    const modal = document.getElementById('settingsModal');
    modal.classList.toggle('active');
}

function updateRangeValue(input, displayId) {
    document.getElementById(displayId).textContent = input.value;
}

function saveSettings() {
    // 這裡可以實作儲存設定到 localStorage 或後端的邏輯
    const model = document.getElementById('llmModel').value;
    const temp = document.getElementById('llmTemperature').value;
    const apiKey = document.getElementById('llmApiKey').value;
    const systemPrompt = document.getElementById('systemPrompt').value;

    console.log('Settings saved:', { model, temp, apiKey, systemPrompt });

    // 模擬儲存成功
    alert('設定已儲存！');
    toggleSettingsModal();
}

// ========== 知識圖譜邏輯 ==========

// 從 PDF 提取的知識數據
let extractedKnowledge = {
    nodes: [],
    edges: []
};

// 下一個節點 ID
let nextNodeId = 100;

/**
 * 從後端 API 載入已存儲的知識
 */
async function loadStoredKnowledge() {
    try {
        const response = await fetch('/api/knowledge-graph');
        if (!response.ok) return;

        const data = await response.json();

        // 更新統計信息顯示
        if (data.stats) {
            updateGraphStats(data.stats);
        }

        // 如果有已存儲的知識，載入到 extractedKnowledge
        if (data.nodes && data.nodes.length > 0) {
            extractedKnowledge.nodes = data.nodes.map(node => ({
                id: node.id,
                label: node.label,
                group: node.group || 'entity',
                value: node.group === 'document' ? 15 : 10,
                title: node.label
            }));

            extractedKnowledge.edges = data.edges.map(edge => ({
                from: edge.from,
                to: edge.to,
                label: edge.label || ''
            }));

            // 更新 nextNodeId 避免衝突
            const maxId = Math.max(...extractedKnowledge.nodes.map(n => n.id), 100);
            nextNodeId = maxId + 1;

            console.log(`[Knowledge] 已載入 ${extractedKnowledge.nodes.length} 個節點`);

            // 重新初始化圖譜
            initGraph();
        }
    } catch (error) {
        console.log('[Knowledge] 載入知識時發生錯誤:', error);
    }
}

/**
 * 更新知識圖譜統計信息顯示
 */
function updateGraphStats(stats) {
    const statDocuments = document.getElementById('statDocuments');
    const statNodes = document.getElementById('statNodes');
    const statEdges = document.getElementById('statEdges');
    const statVectors = document.getElementById('statVectors');
    const statQdrantStatus = document.getElementById('statQdrantStatus');

    if (statDocuments) statDocuments.textContent = stats.documents_count || 0;
    if (statNodes) statNodes.textContent = stats.nodes_count || 0;
    if (statEdges) statEdges.textContent = stats.edges_count || 0;
    if (statVectors) statVectors.textContent = stats.vectors_count || 0;

    if (statQdrantStatus) {
        const status = stats.qdrant_status || 'unknown';
        statQdrantStatus.textContent = status;
        statQdrantStatus.className = 'stat-value status-badge status-' + status;
    }
}

/**
 * 初始化知識圖譜
 */
function initGraph() {
    const container = document.getElementById('knowledgeGraph');
    if (!container) return;

    // 只使用從 PDF 提取的知識數據（不再有 mock data）
    const allNodes = extractedKnowledge.nodes.map(node => ({
        ...node,
        // 只有文檔節點顯示標籤，其他節點懸停顯示
        font: node.group === 'document' ? { size: 12, color: '#ffffff' } : { size: 0, color: 'transparent' },
        title: `${node.label}\n${node.title || ''}`
    }));
    const allEdges = extractedKnowledge.edges;

    // 如果沒有數據，顯示空狀態提示
    if (allNodes.length === 0) {
        container.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--text-muted);">
                <span style="font-size: 48px; margin-bottom: 16px;">🕸️</span>
                <p>尚無知識圖譜數據</p>
                <p style="font-size: 0.9rem;">上傳 PDF 文件後，提取的知識將顯示在此處</p>
            </div>
        `;
        return;
    }

    // 清除空狀態
    if (!network) {
        container.innerHTML = '';
    }

    const nodes = new vis.DataSet(allNodes);
    const edges = new vis.DataSet(allEdges);

    graphData = { nodes, edges };

    const options = {
        nodes: {
            shape: 'dot',
            scaling: { min: 15, max: 40 },
            borderWidth: 3,
            shadow: true,
            font: {
                size: 12,
                face: 'Inter, sans-serif',
                color: '#ffffff',
                strokeWidth: 2,
                strokeColor: 'rgba(0,0,0,0.5)'
            }
        },
        edges: {
            width: 2,
            color: { inherit: 'from', opacity: 0.4 },
            smooth: {
                type: 'curvedCW',
                roundness: 0.2
            },
            arrows: {
                to: { enabled: true, scaleFactor: 0.5 }
            }
        },
        physics: {
            enabled: true,
            stabilization: {
                enabled: true,
                iterations: 200,
                updateInterval: 25
            },
            barnesHut: {
                gravitationalConstant: -2000,  // 減少引力，讓節點更分散
                centralGravity: 0.1,           // 降低中心引力，允許更自由漂移
                springConstant: 0.01,          // 降低彈簧常數，更柔和的連接
                springLength: 180,             // 增加預設連線長度
                damping: 0.15,                 // 降低阻尼，讓運動更緩慢平滑
                avoidOverlap: 0.3
            },
            minVelocity: 0.1,                  // 極低的最小速度，讓節點緩慢漂移直到自然停止
            maxVelocity: 30,                   // 限制最大速度
            solver: 'barnesHut',
            timestep: 0.5                      // 較慢的時間步長，運動更平滑
        },

        interaction: {
            tooltipDelay: 100,
            hover: true,
            hideEdgesOnDrag: false,
            hideEdgesOnZoom: false,
            navigationButtons: true,
            keyboard: true,
            dragNodes: true,
            dragView: true
        },
        groups: {
            core: { color: { background: '#667eea', border: '#5a67d8' }, size: 30 },
            tech: { color: { background: '#48bb78', border: '#38a169' }, size: 22 },
            concept: { color: { background: '#ed8936', border: '#dd6b20' }, size: 20 },
            field: { color: { background: '#9f7aea', border: '#805ad5' }, size: 22 },
            model: { color: { background: '#f56565', border: '#e53e3e' }, size: 24 },
            document: {
                color: { background: '#4299e1', border: '#3182ce' },
                size: 28,
                font: { size: 11, color: '#ffffff' }
            },
            entity: { color: { background: '#38b2ac', border: '#319795' }, size: 18 },
            error: { color: { background: '#e53e3e', border: '#c53030' }, size: 15 }
        }
    };

    if (network) {
        network.setData(graphData);
        network.setOptions(options);
    } else {
        network = new vis.Network(container, graphData, options);

        // 懸停時顯示節點標籤
        network.on('hoverNode', (params) => {
            const nodeId = params.node;
            const node = graphData.nodes.get(nodeId);
            if (node && node.group !== 'document') {
                graphData.nodes.update({
                    id: nodeId,
                    font: { size: 12, color: '#ffffff', strokeWidth: 2, strokeColor: 'rgba(0,0,0,0.7)' }
                });
            }
        });

        network.on('blurNode', (params) => {
            const nodeId = params.node;
            const node = graphData.nodes.get(nodeId);
            if (node && node.group !== 'document') {
                graphData.nodes.update({
                    id: nodeId,
                    font: { size: 0, color: 'transparent' }
                });
            }
        });
    }

    // 套用當前主題顏色
    const currentTheme = document.documentElement.getAttribute('data-theme');
    updateGraphTheme(currentTheme);
}

/**
 * 從 PDF 處理結果添加知識到圖譜
 */
function addKnowledgeToGraph(documentName, entities, relations) {
    // 創建文檔節點
    const docNodeId = nextNodeId++;
    extractedKnowledge.nodes.push({
        id: docNodeId,
        label: documentName,
        group: 'document',
        value: 15,
        title: `文件: ${documentName}`
    });

    // 創建實體節點
    const entityIdMap = {};
    entities.forEach(entity => {
        const nodeId = nextNodeId++;
        entityIdMap[entity.name] = nodeId;

        extractedKnowledge.nodes.push({
            id: nodeId,
            label: entity.name,
            group: entity.type || 'entity',
            value: 10,
            title: entity.description || entity.name
        });

        // 連接到文檔
        extractedKnowledge.edges.push({
            from: docNodeId,
            to: nodeId,
            label: '包含'
        });
    });

    // 創建關係邊
    relations.forEach(rel => {
        const fromId = entityIdMap[rel.from];
        const toId = entityIdMap[rel.to];
        if (fromId && toId) {
            extractedKnowledge.edges.push({
                from: fromId,
                to: toId,
                label: rel.relation || ''
            });
        }
    });

    // 如果圖譜已初始化，動態添加（檢查是否已存在）
    if (graphData && graphData.nodes) {
        try {
            const docNode = extractedKnowledge.nodes[extractedKnowledge.nodes.length - entities.length - 1];
            // 檢查節點是否已存在
            if (docNode && !graphData.nodes.get(docNode.id)) {
                graphData.nodes.add(docNode);
            }

            entities.forEach((entity, i) => {
                const node = extractedKnowledge.nodes[extractedKnowledge.nodes.length - entities.length + i];
                // 檢查節點是否已存在
                if (node && !graphData.nodes.get(node.id)) {
                    graphData.nodes.add(node);
                }
            });

            extractedKnowledge.edges.slice(-relations.length - entities.length).forEach(edge => {
                // 檢查邊是否已存在
                if (!graphData.edges.get(edge.id)) {
                    graphData.edges.add(edge);
                }
            });

            if (network) {
                network.fit();
            }
        } catch (e) {
            console.warn('[Graph] 添加節點時發生非關鍵錯誤:', e.message);
        }
    }

    console.log(`已添加 ${entities.length} 個實體和 ${relations.length} 個關係到知識圖譜`);
}

/**
 * 更新圖譜主題顏色
 */
function updateGraphTheme(theme) {
    if (!network) return;

    const isLight = theme === 'light';
    const textColor = isLight ? '#1a1a2e' : '#ffffff';

    const options = {
        nodes: { font: { color: textColor } }
    };

    network.setOptions(options);
}

/**
 * 重新整理圖譜
 */
function refreshGraph() {
    // 重新初始化圖譜
    network = null;
    initGraph();
}

// ========== 工具函數 ==========

/**
 * 生成唯一的客戶端 ID
 */
function generateClientId() {
    return 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

/**
 * 更新連接狀態顯示
 */
function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connectionStatus');
    const dot = statusElement.querySelector('.status-dot');
    const text = statusElement.querySelector('.status-text');

    dot.classList.remove('connected', 'disconnected');

    switch (status) {
        case 'connected':
            dot.classList.add('connected');
            text.textContent = '已連接';
            break;
        case 'disconnected':
            dot.classList.add('disconnected');
            text.textContent = '已斷開';
            break;
        case 'connecting':
            text.textContent = '連接中...';
            break;
    }
}

/**
 * 滾動到最新訊息
 */
function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 100);
}

/**
 * 自動調整輸入框高度
 */
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
}

/**
 * 處理鍵盤事件
 */
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

/**
 * 簡易 Markdown 轉 HTML
 */
function parseMarkdown(text) {
    // 處理思考區塊 - 合併所有 <think> 內容到一個區塊
    // 先收集所有 think 內容
    let thinkContents = [];
    let hasOpenThink = false;

    // 匹配完整的 think 區塊
    text = text.replace(/<think>([\s\S]*?)<\/think>/g, (match, content) => {
        thinkContents.push(content.trim());
        return ''; // 先移除，稍後統一添加
    });

    // 檢查是否有未閉合的 think 標籤（串流中）
    const openThinkMatch = text.match(/<think>([\s\S]*)$/);
    if (openThinkMatch) {
        hasOpenThink = true;
        thinkContents.push(openThinkMatch[1].trim());
        text = text.replace(/<think>[\s\S]*$/, '');
    }

    // 如果有思考內容，生成單一思考區塊
    let thinkBlock = '';
    if (thinkContents.length > 0) {
        // 合併思考內容，每段之間用分隔線
        const combinedContent = thinkContents.join('\n\n---\n\n');
        const thinkId = 'think_block';  // 使用固定 ID
        const statusText = hasOpenThink ? '思考中...' : '思考過程';
        const statusClass = hasOpenThink ? 'thinking' : '';

        // 對思考內容應用 markdown 轉換
        let formattedThink = combinedContent
            // 程式碼區塊
            .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
            // 行內程式碼
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // 粗體
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // 斜體
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            // 分隔線
            .replace(/---/g, '<hr class="think-divider">')
            // 換行
            .replace(/\n/g, '<br>');

        thinkBlock = `
            <div class="think-block ${statusClass}">
                <button class="think-toggle" onclick="toggleThink('${thinkId}')">
                    <span class="arrow">▼</span> ${statusText}
                </button>
                <div class="think-content" id="${thinkId}">${formattedThink}</div>
            </div>
        `;
    }

    // 程式碼區塊
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>');

    // 行內程式碼
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 粗體
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // 斜體
    text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // 連結
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

    // 換行
    text = text.replace(/\n/g, '<br>');

    // 將思考區塊放在最前面
    return thinkBlock + text;
}

/**
 * 切換思考區塊展開/收合
 */
function toggleThink(id) {
    const content = document.getElementById(id);
    const button = content.previousElementSibling;

    content.classList.toggle('collapsed');
    button.classList.toggle('collapsed');
}

// ========== WebSocket 連接管理 ==========

/**
 * 建立 WebSocket 連接
 */
function connectWebSocket() {
    updateConnectionStatus('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${clientId}`;

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket 已連接');
            isConnected = true;
            reconnectAttempts = 0;
            updateConnectionStatus('connected');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        };

        ws.onclose = () => {
            console.log('WebSocket 已斷開');
            isConnected = false;
            updateConnectionStatus('disconnected');

            // 嘗試重新連接
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                console.log(`嘗試重新連接... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                setTimeout(connectWebSocket, RECONNECT_DELAY);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket 錯誤:', error);
        };

    } catch (error) {
        console.error('建立 WebSocket 連接失敗:', error);
        updateConnectionStatus('disconnected');
    }
}

/**
 * 處理伺服器訊息
 */
function handleServerMessage(data) {
    switch (data.type) {
        case 'status':
            // 處理狀態訊息
            console.log('狀態:', data.message);
            break;

        case 'stream_start':
            // 開始串流
            currentMessageContent = '';
            currentAssistantMessage = createAssistantMessage();
            hideWelcomeMessage();
            break;

        case 'stream':
            // 接收串流片段
            if (currentAssistantMessage) {
                currentMessageContent += data.content;
                updateAssistantMessage(currentMessageContent);
            }
            break;

        case 'stream_end':
            // 串流結束
            if (currentAssistantMessage) {
                finalizeAssistantMessage(data.full_content || currentMessageContent);
            }
            currentAssistantMessage = null;
            currentMessageContent = '';
            break;

        case 'tool_call':
            // 工具呼叫
            showToolStatus(data.name, data.args || '');
            break;

        case 'tool_response':
            // 工具回應 - 標記工具完成
            markToolComplete(data.name);
            break;

        case 'error':
            // 錯誤訊息
            showErrorMessage(data.message);
            break;

        case 'pong':
            // 心跳回應
            break;

        case 'upload_progress':
            // 文件上傳進度更新
            handleUploadProgress(data);
            break;
    }
}

// ========== 訊息處理 ==========

/**
 * 隱藏歡迎訊息
 */
function hideWelcomeMessage() {
    const welcome = document.querySelector('.welcome-message');
    if (welcome) {
        welcome.style.display = 'none';
    }
}

/**
 * 發送訊息
 */
function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    // 檢查是否有訊息或圖片
    if ((!message && pendingImages.length === 0) || !isConnected) return;

    // 清空輸入框
    input.value = '';
    autoResize(input);

    // 隱藏歡迎訊息
    hideWelcomeMessage();

    // 顯示用戶訊息（包含圖片）
    addUserMessage(message, pendingImages.slice());

    // 準備圖片數據
    const images = pendingImages.map(img => ({
        data: img.data,
        type: img.type,
        name: img.name
    }));

    // 發送到伺服器
    ws.send(JSON.stringify({
        type: 'message',
        content: message,
        images: images
    }));

    // 清空預覽圖片
    clearAllImages();

    // 顯示打字動畫
    showTypingIndicator();
}

/**
 * 發送快捷訊息
 */
function sendQuickMessage(message) {
    document.getElementById('messageInput').value = message;
    sendMessage();
}

/**
 * 添加用戶訊息到聊天區域
 */
function addUserMessage(content, images = []) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';

    // 構建圖片 HTML
    let imagesHtml = '';
    if (images.length > 0) {
        imagesHtml = '<div class="message-images">' +
            images.map(img => `<img src="${img.data}" alt="${img.name}" class="message-image">`).join('') +
            '</div>';
    }

    // 構建訊息內容
    let contentHtml = content ? `<div class="message-text">${escapeHtml(content)}</div>` : '';

    messageDiv.innerHTML = `
        <div class="message-avatar">👤</div>
        <div class="message-content">${imagesHtml}${contentHtml}</div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ========== 工具狀態顯示 ==========

/**
 * 顯示工具使用狀態（顯示在 AI 訊息內部）
 */
function showToolStatus(toolName, args = '') {
    // 如果沒有當前的 AI 訊息，先創建一個
    if (!currentAssistantMessage) {
        currentAssistantMessage = createAssistantMessage();
        hideWelcomeMessage();
    }

    const contentDiv = currentAssistantMessage.querySelector('.message-content');
    if (!contentDiv) return;

    // 檢查是否已有工具狀態區域
    let toolArea = contentDiv.querySelector('.tool-area');
    if (!toolArea) {
        toolArea = document.createElement('div');
        toolArea.className = 'tool-area';
        contentDiv.insertBefore(toolArea, contentDiv.firstChild);
    }

    // 添加新的工具標籤
    const toolTag = document.createElement('span');
    toolTag.className = 'tool-tag loading';
    toolTag.id = `tool-${toolName.replace(/\s+/g, '_')}`;
    toolTag.innerHTML = `<span class="tool-dot"></span>${toolName}`;
    toolArea.appendChild(toolTag);

    scrollToBottom();
}

/**
 * 更新工具回應狀態
 */
function showToolResponse(toolName, response = '') {
    const toolId = `tool-${toolName.replace(/\s+/g, '_')}`;
    const toolTag = document.getElementById(toolId);

    if (toolTag) {
        toolTag.classList.remove('loading');
        toolTag.classList.add('completed');
    }
}

/**
 * 隱藏工具狀態
 */
function hideToolStatus() {
    const statusContainer = document.getElementById('toolStatusContainer');
    if (statusContainer) {
        statusContainer.style.display = 'none';
    }
}

/**
 * 創建助手訊息容器
 */
function createAssistantMessage() {
    hideTypingIndicator();

    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content"></div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

/**
 * 更新助手訊息內容（串流中）
 */
function updateAssistantMessage(content) {
    if (!currentAssistantMessage) return;

    const contentDiv = currentAssistantMessage.querySelector('.message-content');
    contentDiv.innerHTML = parseMarkdown(content);

    // 讓思考區塊自動滾動到底部
    const thinkContent = contentDiv.querySelector('.think-content');
    if (thinkContent) {
        thinkContent.scrollTop = thinkContent.scrollHeight;
    }

    scrollToBottom();
}

/**
 * 完成助手訊息
 */
function finalizeAssistantMessage(content) {
    if (!currentAssistantMessage) return;

    const contentDiv = currentAssistantMessage.querySelector('.message-content');
    contentDiv.innerHTML = parseMarkdown(content);

    // 自動收合思考區塊
    const thinkContents = contentDiv.querySelectorAll('.think-content');
    thinkContents.forEach(el => {
        el.classList.add('collapsed');
        el.previousElementSibling.classList.add('collapsed');
    });

    scrollToBottom();
}

/**
 * 顯示打字動畫
 */
function showTypingIndicator() {
    hideTypingIndicator();

    const chatMessages = document.getElementById('chatMessages');

    const typingDiv = document.createElement('div');
    typingDiv.id = 'typingIndicator';
    typingDiv.className = 'message assistant';
    typingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;

    chatMessages.appendChild(typingDiv);
    scrollToBottom();
}

/**
 * 隱藏打字動畫
 */
function hideTypingIndicator() {
    const typing = document.getElementById('typingIndicator');
    if (typing) {
        typing.remove();
    }
}

/**
 * 顯示工具使用狀態 (在當前 assistant 訊息下方)
 * @param {string} toolName - 工具名稱
 * @param {string} args - 工具參數 (可選)
 */
function showToolStatus(toolName, args = '') {
    // 找到當前的 assistant 訊息，或創建一個新的
    let targetMessage = currentAssistantMessage;

    if (!targetMessage) {
        // 如果沒有當前訊息，找最後一個 assistant 訊息
        const messages = document.querySelectorAll('.message.assistant');
        if (messages.length > 0) {
            targetMessage = messages[messages.length - 1];
        }
    }

    if (!targetMessage) {
        // 還是沒有就創建一個
        targetMessage = createAssistantMessage();
        currentAssistantMessage = targetMessage;
    }

    // 查找或創建工具指示器容器
    let indicatorsContainer = targetMessage.querySelector('.tool-indicators');
    if (!indicatorsContainer) {
        indicatorsContainer = document.createElement('div');
        indicatorsContainer.className = 'tool-indicators';
        targetMessage.appendChild(indicatorsContainer);
    }

    // 檢查該工具是否已存在
    const existingIndicator = indicatorsContainer.querySelector(`[data-tool="${toolName}"]`);
    if (existingIndicator) {
        // 如果存在，更新參數顯示
        return;
    }

    // 創建新的工具指示器
    const indicator = document.createElement('div');
    indicator.className = 'tool-indicator';
    indicator.setAttribute('data-tool', toolName);
    indicator.innerHTML = `
        <span class="tool-icon">⚡</span>
        <span class="tool-text">正在使用 ${escapeHtml(toolName)}</span>
    `;

    indicatorsContainer.appendChild(indicator);
    scrollToBottom();
}

/**
 * 標記工具完成
 * @param {string} toolName - 工具名稱
 */
function markToolComplete(toolName) {
    const indicator = document.querySelector(`.tool-indicator[data-tool="${toolName}"]`);
    if (indicator) {
        indicator.classList.add('completed');
        indicator.querySelector('.tool-icon').textContent = '✓';
        indicator.querySelector('.tool-text').textContent = `${toolName} 完成`;

        // 3 秒後淡出移除
        setTimeout(() => {
            indicator.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            indicator.style.opacity = '0';
            indicator.style.transform = 'scale(0.8)';
            setTimeout(() => indicator.remove(), 500);
        }, 2000);
    }
}

/**
 * 隱藏所有工具狀態
 */
function hideToolStatus() {
    const indicators = document.querySelectorAll('.tool-indicators');
    indicators.forEach(container => {
        container.style.transition = 'opacity 0.3s ease';
        container.style.opacity = '0';
        setTimeout(() => container.remove(), 300);
    });
}

/**
 * 顯示錯誤訊息
 */
function showErrorMessage(message) {
    hideTypingIndicator();

    const chatMessages = document.getElementById('chatMessages');

    const errorDiv = document.createElement('div');
    errorDiv.className = 'message assistant';
    errorDiv.innerHTML = `
        <div class="message-avatar">⚠️</div>
        <div class="message-content" style="border-color: rgba(244, 67, 54, 0.5); color: #ff6b6b;">
            錯誤：${escapeHtml(message)}
        </div>
    `;

    chatMessages.appendChild(errorDiv);
    scrollToBottom();
}

/**
 * HTML 跳脫
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== 心跳機制 ==========

/**
 * 發送心跳
 */
function sendHeartbeat() {
    if (isConnected && ws) {
        ws.send(JSON.stringify({ type: 'ping' }));
    }
}

// 每 30 秒發送一次心跳
setInterval(sendHeartbeat, 30000);

// ========== 初始化 ==========

// 頁面載入時連接 WebSocket
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    initTheme();
    initPDFUpload(); // 初始化 PDF 上傳功能
    loadStoredKnowledge(); // 載入已存儲的知識

    // 聚焦到輸入框
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.focus();
        // 監聽 Ctrl+V 貼上圖片 (只在輸入框)
        messageInput.addEventListener('paste', handlePaste);
    }


    // 點擊外部關閉模態框
    document.getElementById('settingsModal').addEventListener('click', (e) => {
        if (e.target.id === 'settingsModal') {
            toggleSettingsModal();
        }
    });

    // 點擊外部關閉側邊欄 (手機版)
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768) {
            const sidebar = document.getElementById('sidebar');
            const toggleBtn = document.querySelector('.mobile-menu-btn');

            if (sidebar.classList.contains('active') &&
                !sidebar.contains(e.target) &&
                e.target !== toggleBtn) {
                sidebar.classList.remove('active');
            }
        }
    });
});

// 頁面關閉時斷開連接
window.addEventListener('beforeunload', () => {
    if (ws) {
        ws.close();
    }
});
