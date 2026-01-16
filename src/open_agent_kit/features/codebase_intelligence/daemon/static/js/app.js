const API_BASE = '';
const DEBUG = false;  // Set to true for verbose logging
function debug(...args) { if (DEBUG) console.log('[CI]', ...args); }

// ============================================================================
// State Variables (must be defined before any code that uses them)
// ============================================================================

var memoriesState = {
    offset: 0,
    limit: 20,
    typeFilter: null,
    total: 0
};

var sessionsState = {
    offset: 0,
    limit: 10,
    statusFilter: null,
    total: 0
};

var activitiesState = {
    sessionId: null,
    offset: 0,
    limit: 50,
    toolFilter: null,
    total: 0
};

// ============================================================================
// Tab Switching
// ============================================================================

// Switch to a specific tab by name
function switchToTab(tabName) {
    var validTabs = ['search', 'memory', 'activity', 'settings'];
    if (!validTabs.includes(tabName)) {
        tabName = 'search';
    }

    // Update tab buttons
    document.querySelectorAll('.tab').forEach(function (t) {
        t.classList.remove('active');
        if (t.dataset.tab === tabName) {
            t.classList.add('active');
        }
    });

    // Show/hide tab content
    document.getElementById('search-tab').style.display = tabName === 'search' ? 'block' : 'none';
    document.getElementById('memory-tab').style.display = tabName === 'memory' ? 'block' : 'none';
    document.getElementById('activity-tab').style.display = tabName === 'activity' ? 'block' : 'none';
    document.getElementById('settings-tab').style.display = tabName === 'settings' ? 'block' : 'none';

    // Load tab content
    if (tabName === 'settings') loadConfig();
    if (tabName === 'memory') loadMemories();
    if (tabName === 'activity') loadSessions();
}

// Tab switching via click
document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
        var tabId = tab.dataset.tab;
        switchToTab(tabId);
        // Update URL without reload
        var url = new URL(window.location);
        url.searchParams.set('tab', tabId);
        window.history.replaceState({}, '', url);
    });
});

// Check URL params on load and switch to requested tab
(function checkUrlParams() {
    var params = new URLSearchParams(window.location.search);
    var tab = params.get('tab');
    if (tab) {
        switchToTab(tab);
    }
})();

// Fetch and display status
async function fetchStatus() {
    try {
        var response = await fetch(API_BASE + '/api/status');
        var data = await response.json();

        document.getElementById('status-text').textContent = data.indexing ? 'Indexing...' : 'Ready';
        var statusDot = document.getElementById('status-dot');
        statusDot.className = 'status-dot' + (data.indexing ? ' indexing' : '');

        document.getElementById('files-count').textContent = (data.index_stats && data.index_stats.files_indexed) || 0;
        document.getElementById('chunks-count').textContent = ((data.index_stats && data.index_stats.chunks_indexed) || 0).toLocaleString();
        document.getElementById('memories-count').textContent = (data.index_stats && data.index_stats.memories_stored) || 0;

        // Display AST chunking statistics
        var astStats = data.index_stats && data.index_stats.ast_stats;
        if (astStats && (astStats.ast_success || astStats.ast_fallback || astStats.line_based)) {
            var astText = 'AST: ' + (astStats.ast_success || 0);
            if (astStats.ast_fallback) {
                astText += ' | Fallback: ' + astStats.ast_fallback;
            }
            if (astStats.line_based) {
                astText += ' | Lines: ' + astStats.line_based;
            }
            document.getElementById('ast-stats').textContent = astText;
        } else {
            document.getElementById('ast-stats').textContent = '';
        }

        document.getElementById('provider-name').textContent = data.embedding_provider || 'Unknown';

        // Show provider usage stats if available
        if (data.embedding_stats && data.embedding_stats.providers) {
            var statsText = data.embedding_stats.providers.map(function (p) {
                var usage = p.usage || { success: 0, failure: 0 };
                var total = usage.success + usage.failure;
                if (total === 0) return p.name.split(':')[0] + ': 0';
                var pct = Math.round((usage.success / total) * 100);
                return p.name.split(':')[0] + ': ' + usage.success + ' (' + pct + '%)';
            }).join(' | ');
            document.getElementById('provider-status').textContent = statsText || 'active';
        } else {
            document.getElementById('provider-status').textContent = data.embedding_provider ? 'active' : 'not available';
        }

        if (data.index_stats && data.index_stats.last_indexed) {
            var date = new Date(data.index_stats.last_indexed);
            document.getElementById('last-indexed').textContent = date.toLocaleTimeString();
            document.getElementById('index-duration').textContent =
                ((data.index_stats.duration_seconds || 0).toFixed(1)) + 's';
        }

        // Set project name from project_root path
        if (data.project_root) {
            var projectName = data.project_root.split('/').pop() || 'Unknown Project';
            document.getElementById('project-name').textContent = projectName;
        } else {
            document.getElementById('project-name').textContent = 'Open Agent Kit';
        }
    } catch (error) {
        document.getElementById('status-text').textContent = 'Error';
        console.error('Failed to fetch status:', error);
    }
}

// Create result element using safe DOM methods
function createCodeResultElement(result) {
    var item = document.createElement('div');
    item.className = 'result-item';
    item.dataset.id = result.id;

    var header = document.createElement('div');
    header.className = 'result-header';

    var typeSpan = document.createElement('span');
    typeSpan.className = 'result-type';
    typeSpan.textContent = result.type || 'code';

    var nameSpan = document.createElement('span');
    nameSpan.className = 'result-name';
    nameSpan.textContent = result.name || 'unnamed';

    var relevanceSpan = document.createElement('span');
    relevanceSpan.className = 'result-relevance';
    relevanceSpan.textContent = Math.round(result.relevance * 100) + '%';

    header.appendChild(typeSpan);
    header.appendChild(nameSpan);
    header.appendChild(relevanceSpan);

    var pathDiv = document.createElement('div');
    pathDiv.className = 'result-path';
    pathDiv.textContent = (result.filepath || '') + ' : ' + (result.lines || '');

    item.appendChild(header);
    item.appendChild(pathDiv);

    return item;
}

function createMemoryResultElement(result) {
    var item = document.createElement('div');
    item.className = 'result-item';
    item.dataset.id = result.id;

    var header = document.createElement('div');
    header.className = 'result-header';

    var typeSpan = document.createElement('span');
    typeSpan.className = 'result-type';
    typeSpan.textContent = result.type || 'memory';

    var relevanceSpan = document.createElement('span');
    relevanceSpan.className = 'result-relevance';
    relevanceSpan.textContent = Math.round(result.relevance * 100) + '%';

    header.appendChild(typeSpan);
    header.appendChild(relevanceSpan);

    var previewDiv = document.createElement('div');
    previewDiv.className = 'result-preview';
    previewDiv.textContent = result.summary || '';

    item.appendChild(header);
    item.appendChild(previewDiv);

    return item;
}

function createLoadingElement() {
    var loading = document.createElement('div');
    loading.className = 'loading';

    var spinner = document.createElement('div');
    spinner.className = 'spinner';

    var text = document.createTextNode('Searching...');

    loading.appendChild(spinner);
    loading.appendChild(text);

    return loading;
}

function createEmptyStateElement(message) {
    var empty = document.createElement('div');
    empty.className = 'empty-state';

    var icon = document.createElement('div');
    icon.className = 'empty-state-icon';
    icon.textContent = '\\uD83D\\uDD0D';

    var msg = document.createElement('p');
    msg.textContent = message;

    empty.appendChild(icon);
    empty.appendChild(msg);

    return empty;
}

// Search functionality
async function performSearch() {
    var query = document.getElementById('search-input').value.trim();
    if (!query) return;

    var searchType = document.getElementById('search-type').value;
    var resultsSection = document.getElementById('results-section');
    var resultsContainer = document.getElementById('results-container');

    resultsSection.style.display = 'block';

    // Clear container and show loading
    while (resultsContainer.firstChild) {
        resultsContainer.removeChild(resultsContainer.firstChild);
    }
    resultsContainer.appendChild(createLoadingElement());

    try {
        var response = await fetch(API_BASE + '/api/search?query=' + encodeURIComponent(query) +
            '&search_type=' + searchType + '&limit=20');
        var data = await response.json();

        var codeResults = data.code || [];
        var memoryResults = data.memory || [];
        var total = codeResults.length + memoryResults.length;

        document.getElementById('results-count').textContent = total + ' results';

        // Clear container
        while (resultsContainer.firstChild) {
            resultsContainer.removeChild(resultsContainer.firstChild);
        }

        if (total === 0) {
            resultsContainer.appendChild(createEmptyStateElement('No results found for "' + query + '"'));
            return;
        }

        codeResults.forEach(function (result) {
            resultsContainer.appendChild(createCodeResultElement(result));
        });

        memoryResults.forEach(function (result) {
            resultsContainer.appendChild(createMemoryResultElement(result));
        });

    } catch (error) {
        while (resultsContainer.firstChild) {
            resultsContainer.removeChild(resultsContainer.firstChild);
        }
        resultsContainer.appendChild(createEmptyStateElement('Search failed: ' + error.message));
    }
}

// Save memory
async function saveMemory() {
    var type = document.getElementById('memory-type').value;
    var observation = document.getElementById('memory-observation').value.trim();
    var context = document.getElementById('memory-context').value.trim();

    if (!observation) {
        alert('Please enter an observation');
        return;
    }

    try {
        var body = {
            memory_type: type,
            observation: observation
        };
        if (context) {
            body.context = context;
        }

        var response = await fetch(API_BASE + '/api/remember', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (response.ok) {
            document.getElementById('memory-observation').value = '';
            document.getElementById('memory-context').value = '';
            alert('Memory saved successfully!');
            fetchStatus();
            // Refresh memories list to show the new memory
            memoriesState.offset = 0;
            loadMemories();
        } else {
            var error = await response.json();
            alert('Failed to save memory: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to save memory: ' + error.message);
    }
}

// ============================================================================
// Memories Browser
// ============================================================================

// Memory type icons
var memoryTypeIcons = {
    'gotcha': '⚠️',
    'bug_fix': '🐛',
    'decision': '📐',
    'discovery': '💡',
    'trade_off': '⚖️',
    'session_summary': '📋'
};

function createMemoryListItem(memory) {
    var item = document.createElement('div');
    item.className = 'result-item';
    item.style.padding = '0.75rem';
    item.style.marginBottom = '0.5rem';

    var memType = memory.memory_type || 'discovery';
    var icon = memoryTypeIcons[memType] || '📝';
    var observation = memory.observation || '';

    // Header with type and icon
    var header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'flex-start';
    header.style.marginBottom = '0.25rem';

    var typeSpan = document.createElement('span');
    typeSpan.style.fontWeight = 'bold';
    typeSpan.style.fontSize = '0.75rem';
    typeSpan.style.textTransform = 'uppercase';
    typeSpan.textContent = icon + ' ' + memType.replace('_', ' ');

    var dateSpan = document.createElement('span');
    dateSpan.style.fontSize = '0.7rem';
    dateSpan.style.color = 'var(--text-secondary)';
    if (memory.created_at) {
        try {
            var dt = new Date(memory.created_at);
            dateSpan.textContent = dt.toLocaleDateString() + ' ' + dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } catch (e) {
            dateSpan.textContent = memory.created_at;
        }
    }

    header.appendChild(typeSpan);
    header.appendChild(dateSpan);

    // Observation text
    var obsDiv = document.createElement('div');
    obsDiv.style.fontSize = '0.875rem';
    obsDiv.style.lineHeight = '1.4';
    // Truncate long observations
    if (observation.length > 200) {
        obsDiv.textContent = observation.substring(0, 197) + '...';
        obsDiv.title = observation;
    } else {
        obsDiv.textContent = observation;
    }

    item.appendChild(header);
    item.appendChild(obsDiv);

    // Context if available
    if (memory.context) {
        var ctxDiv = document.createElement('div');
        ctxDiv.style.fontSize = '0.75rem';
        ctxDiv.style.color = 'var(--text-secondary)';
        ctxDiv.style.marginTop = '0.25rem';
        ctxDiv.textContent = 'Context: ' + memory.context;
        item.appendChild(ctxDiv);
    }

    // Tags if available
    if (memory.tags && memory.tags.length > 0) {
        var tagsDiv = document.createElement('div');
        tagsDiv.style.fontSize = '0.7rem';
        tagsDiv.style.color = 'var(--text-secondary)';
        tagsDiv.style.marginTop = '0.25rem';
        tagsDiv.textContent = 'Tags: ' + memory.tags.join(', ');
        item.appendChild(tagsDiv);
    }

    return item;
}

async function loadMemories() {
    var container = document.getElementById('memories-list');
    var paginationEl = document.getElementById('memories-pagination');

    // Show loading
    container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading memories...</div>';

    try {
        var url = API_BASE + '/api/memories?limit=' + memoriesState.limit + '&offset=' + memoriesState.offset;
        if (memoriesState.typeFilter) {
            url += '&memory_type=' + memoriesState.typeFilter;
        }

        var response = await fetch(url);
        var data = await response.json();

        memoriesState.total = data.total || 0;
        var memories = data.memories || [];

        // Clear container
        container.innerHTML = '';

        if (memories.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.style.padding = '2rem';
            empty.style.textAlign = 'center';
            empty.innerHTML = '<div style="font-size: 2rem; margin-bottom: 0.5rem;">📭</div>' +
                '<p style="color: var(--text-secondary);">No memories found</p>';
            container.appendChild(empty);
            paginationEl.style.display = 'none';
            return;
        }

        memories.forEach(function (memory) {
            container.appendChild(createMemoryListItem(memory));
        });

        // Update pagination
        var currentPage = Math.floor(memoriesState.offset / memoriesState.limit) + 1;
        var totalPages = Math.ceil(memoriesState.total / memoriesState.limit);

        document.getElementById('memories-page-info').textContent =
            'Page ' + currentPage + ' of ' + totalPages + ' (' + memoriesState.total + ' total)';

        document.getElementById('memories-prev-btn').disabled = memoriesState.offset === 0;
        document.getElementById('memories-next-btn').disabled =
            memoriesState.offset + memoriesState.limit >= memoriesState.total;

        paginationEl.style.display = 'flex';

    } catch (error) {
        container.innerHTML = '<div class="empty-state" style="padding: 2rem; text-align: center;">' +
            '<p style="color: var(--error);">Failed to load memories: ' + error.message + '</p></div>';
        paginationEl.style.display = 'none';
    }
}

function memoriesNextPage() {
    if (memoriesState.offset + memoriesState.limit < memoriesState.total) {
        memoriesState.offset += memoriesState.limit;
        loadMemories();
    }
}

function memoriesPrevPage() {
    if (memoriesState.offset > 0) {
        memoriesState.offset = Math.max(0, memoriesState.offset - memoriesState.limit);
        loadMemories();
    }
}

function memoriesFilterChanged() {
    var filter = document.getElementById('memories-filter').value;
    memoriesState.typeFilter = filter || null;
    memoriesState.offset = 0;  // Reset to first page
    loadMemories();
}

async function reprocessMemories() {
    var btn = document.getElementById('reprocess-memories-btn');
    var originalText = btn.textContent;

    if (!confirm('This will reprocess all sessions to extract memories.\n\nThis uses the configured summarization LLM to analyze session activities and extract gotchas, decisions, and discoveries.\n\nContinue?')) {
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Processing...';

    try {
        var response = await fetch('/api/activity/reprocess-memories?recover_stuck=true&process_immediately=true', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        var data = await response.json();

        if (data.success) {
            var message = data.message || 'Reprocessing complete';
            alert(message);

            // Refresh memories list and status
            loadMemories();
            fetchStatus();
        } else {
            alert('Reprocessing failed: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Reprocess error:', error);
        alert('Failed to reprocess memories: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// ============================================================================
// Detail Modal
// ============================================================================

function showModal(title, bodyContent) {
    var modal = document.getElementById('detail-modal');
    var modalTitle = document.getElementById('modal-title');
    var modalBody = document.getElementById('modal-body');

    if (!modal || !modalTitle || !modalBody) {
        debug('Modal elements not found');
        return;
    }

    modalTitle.textContent = title;

    // Clear previous content
    modalBody.innerHTML = '';

    // bodyContent can be a string (HTML) or a DOM element
    if (typeof bodyContent === 'string') {
        modalBody.innerHTML = bodyContent;
    } else {
        modalBody.appendChild(bodyContent);
    }

    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function hideModal() {
    var modal = document.getElementById('detail-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Close modal on backdrop click or close button
document.addEventListener('DOMContentLoaded', function() {
    var modal = document.getElementById('detail-modal');
    var closeBtn = document.getElementById('modal-close');

    if (closeBtn) {
        closeBtn.addEventListener('click', hideModal);
    }

    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                hideModal();
            }
        });
    }

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            hideModal();
        }
    });
});

function showActivityDetail(activity) {
    var content = document.createElement('div');

    // Header info
    var headerDiv = document.createElement('div');
    headerDiv.style.marginBottom = '1rem';
    headerDiv.style.paddingBottom = '0.75rem';
    headerDiv.style.borderBottom = '1px solid var(--border-color)';

    var icon = toolIcons[activity.tool_name] || '&#x2699;';
    headerDiv.innerHTML = '<div style="display: flex; justify-content: space-between; align-items: center;">' +
        '<span style="font-weight: bold; font-size: 1.1rem;">' + icon + ' ' + activity.tool_name + '</span>' +
        '<span style="color: ' + (activity.success ? 'var(--success)' : 'var(--error)') + ';">' +
        (activity.success ? '✓ Success' : '✗ Failed') + '</span>' +
        '</div>';

    if (activity.created_at) {
        var timeDiv = document.createElement('div');
        timeDiv.style.color = 'var(--text-secondary)';
        timeDiv.style.fontSize = '0.8rem';
        timeDiv.style.marginTop = '0.25rem';
        var dt = new Date(activity.created_at);
        timeDiv.textContent = dt.toLocaleString();
        headerDiv.appendChild(timeDiv);
    }

    if (activity.file_path) {
        var pathDiv = document.createElement('div');
        pathDiv.style.color = 'var(--text-secondary)';
        pathDiv.style.fontSize = '0.8rem';
        pathDiv.style.marginTop = '0.25rem';
        pathDiv.style.fontFamily = "'SF Mono', SFMono-Regular, Consolas, monospace";
        pathDiv.textContent = activity.file_path;
        headerDiv.appendChild(pathDiv);
    }

    content.appendChild(headerDiv);

    // Tool Input section
    if (activity.tool_input) {
        var inputSection = document.createElement('div');
        inputSection.style.marginBottom = '1rem';

        var inputLabel = document.createElement('div');
        inputLabel.style.fontWeight = 'bold';
        inputLabel.style.marginBottom = '0.5rem';
        inputLabel.style.color = 'var(--text-primary)';
        inputLabel.textContent = 'Input';
        inputSection.appendChild(inputLabel);

        var inputPre = document.createElement('pre');
        inputPre.style.background = 'var(--bg-tertiary)';
        inputPre.style.padding = '0.75rem';
        inputPre.style.borderRadius = '4px';
        inputPre.style.overflow = 'auto';
        inputPre.style.maxHeight = '200px';
        inputPre.style.fontSize = '0.75rem';
        inputPre.style.fontFamily = "'SF Mono', SFMono-Regular, Consolas, monospace";
        inputPre.style.whiteSpace = 'pre-wrap';
        inputPre.style.wordBreak = 'break-all';
        inputPre.textContent = JSON.stringify(activity.tool_input, null, 2);
        inputSection.appendChild(inputPre);

        content.appendChild(inputSection);
    }

    // Tool Output Summary section
    if (activity.tool_output_summary) {
        var outputSection = document.createElement('div');
        outputSection.style.marginBottom = '1rem';

        var outputLabel = document.createElement('div');
        outputLabel.style.fontWeight = 'bold';
        outputLabel.style.marginBottom = '0.5rem';
        outputLabel.style.color = 'var(--text-primary)';
        outputLabel.textContent = 'Output Summary';
        outputSection.appendChild(outputLabel);

        var outputPre = document.createElement('pre');
        outputPre.style.background = 'var(--bg-tertiary)';
        outputPre.style.padding = '0.75rem';
        outputPre.style.borderRadius = '4px';
        outputPre.style.overflow = 'auto';
        outputPre.style.maxHeight = '200px';
        outputPre.style.fontSize = '0.75rem';
        outputPre.style.fontFamily = "'SF Mono', SFMono-Regular, Consolas, monospace";
        outputPre.style.whiteSpace = 'pre-wrap';
        outputPre.style.wordBreak = 'break-all';
        outputPre.textContent = activity.tool_output_summary;
        outputSection.appendChild(outputPre);

        content.appendChild(outputSection);
    }

    // Error Message section
    if (activity.error_message) {
        var errorSection = document.createElement('div');
        errorSection.style.marginBottom = '1rem';

        var errorLabel = document.createElement('div');
        errorLabel.style.fontWeight = 'bold';
        errorLabel.style.marginBottom = '0.5rem';
        errorLabel.style.color = 'var(--error)';
        errorLabel.textContent = 'Error';
        errorSection.appendChild(errorLabel);

        var errorPre = document.createElement('pre');
        errorPre.style.background = 'rgba(255,100,100,0.1)';
        errorPre.style.padding = '0.75rem';
        errorPre.style.borderRadius = '4px';
        errorPre.style.overflow = 'auto';
        errorPre.style.maxHeight = '200px';
        errorPre.style.fontSize = '0.75rem';
        errorPre.style.fontFamily = "'SF Mono', SFMono-Regular, Consolas, monospace";
        errorPre.style.whiteSpace = 'pre-wrap';
        errorPre.style.wordBreak = 'break-all';
        errorPre.style.color = 'var(--error)';
        errorPre.textContent = activity.error_message;
        errorSection.appendChild(errorPre);

        content.appendChild(errorSection);
    }

    // IDs for debugging
    var idSection = document.createElement('div');
    idSection.style.fontSize = '0.7rem';
    idSection.style.color = 'var(--text-secondary)';
    idSection.style.borderTop = '1px solid var(--border-color)';
    idSection.style.paddingTop = '0.5rem';
    idSection.innerHTML = 'ID: ' + activity.id +
        (activity.session_id ? ' | Session: ' + activity.session_id : '') +
        (activity.prompt_batch_id ? ' | Batch: ' + activity.prompt_batch_id : '');
    content.appendChild(idSection);

    showModal('Activity Details', content);
}

function showPromptBatchDetail(batch) {
    var content = document.createElement('div');

    // Header with prompt number and classification
    var headerDiv = document.createElement('div');
    headerDiv.style.marginBottom = '1rem';
    headerDiv.style.paddingBottom = '0.75rem';
    headerDiv.style.borderBottom = '1px solid var(--border-color)';

    var headerHtml = '<div style="display: flex; justify-content: space-between; align-items: center;">' +
        '<span style="font-weight: bold; font-size: 1.1rem;">&#x1F4AC; Prompt #' + batch.prompt_number + '</span>';

    if (batch.classification) {
        var classColors = {
            'exploration': 'var(--info)',
            'implementation': 'var(--success)',
            'debugging': 'var(--warning)',
            'refactoring': 'var(--accent)'
        };
        var color = classColors[batch.classification] || 'var(--text-secondary)';
        headerHtml += '<span style="background: ' + color + '22; color: ' + color + '; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">' + batch.classification + '</span>';
    }
    headerHtml += '</div>';
    headerDiv.innerHTML = headerHtml;

    // Timestamps
    var timeDiv = document.createElement('div');
    timeDiv.style.color = 'var(--text-secondary)';
    timeDiv.style.fontSize = '0.8rem';
    timeDiv.style.marginTop = '0.5rem';

    if (batch.started_at) {
        var startDt = new Date(batch.started_at);
        timeDiv.innerHTML = '<strong>Started:</strong> ' + startDt.toLocaleString();
    }
    if (batch.ended_at) {
        var endDt = new Date(batch.ended_at);
        timeDiv.innerHTML += '<br><strong>Ended:</strong> ' + endDt.toLocaleString();
    }
    if (batch.activity_count) {
        timeDiv.innerHTML += '<br><strong>Activities:</strong> ' + batch.activity_count;
    }
    headerDiv.appendChild(timeDiv);

    content.appendChild(headerDiv);

    // User Prompt section
    var promptSection = document.createElement('div');
    promptSection.style.marginBottom = '1rem';

    var promptLabel = document.createElement('div');
    promptLabel.style.fontWeight = 'bold';
    promptLabel.style.marginBottom = '0.5rem';
    promptLabel.style.color = 'var(--text-primary)';
    promptLabel.textContent = 'User Prompt';
    promptSection.appendChild(promptLabel);

    var promptPre = document.createElement('pre');
    promptPre.style.background = 'var(--bg-tertiary)';
    promptPre.style.padding = '0.75rem';
    promptPre.style.borderRadius = '4px';
    promptPre.style.overflow = 'auto';
    promptPre.style.maxHeight = '400px';
    promptPre.style.fontSize = '0.85rem';
    promptPre.style.fontFamily = "'SF Mono', SFMono-Regular, Consolas, monospace";
    promptPre.style.whiteSpace = 'pre-wrap';
    promptPre.style.wordBreak = 'break-word';
    promptPre.style.lineHeight = '1.5';

    if (batch.user_prompt) {
        promptPre.textContent = batch.user_prompt;
    } else {
        promptPre.textContent = '(No prompt captured)';
        promptPre.style.color = 'var(--text-secondary)';
        promptPre.style.fontStyle = 'italic';
    }
    promptSection.appendChild(promptPre);

    content.appendChild(promptSection);

    // IDs for debugging
    var idSection = document.createElement('div');
    idSection.style.fontSize = '0.7rem';
    idSection.style.color = 'var(--text-secondary)';
    idSection.style.borderTop = '1px solid var(--border-color)';
    idSection.style.paddingTop = '0.5rem';
    idSection.innerHTML = 'Batch ID: ' + batch.id + ' | Session: ' + batch.session_id;
    content.appendChild(idSection);

    showModal('Prompt Details', content);
}

function createPromptBatchListItem(batch) {
    var item = document.createElement('div');
    item.className = 'result-item';
    item.style.padding = '0.5rem 0.75rem';
    item.style.marginBottom = '0.375rem';
    item.style.fontSize = '0.8rem';
    item.style.cursor = 'pointer';
    item.style.transition = 'background-color 0.15s ease';
    item.style.display = 'flex';
    item.style.justifyContent = 'space-between';
    item.style.alignItems = 'center';

    // Click handler to show details
    item.addEventListener('click', function() {
        showPromptBatchDetail(batch);
    });

    // Hover effect
    item.addEventListener('mouseenter', function() {
        item.style.background = 'var(--bg-tertiary)';
    });
    item.addEventListener('mouseleave', function() {
        item.style.background = '';
    });

    // Left side: prompt number and preview
    var leftDiv = document.createElement('div');
    leftDiv.style.flex = '1';
    leftDiv.style.minWidth = '0';

    var numberSpan = document.createElement('span');
    numberSpan.style.fontWeight = 'bold';
    numberSpan.innerHTML = '&#x1F4AC; Prompt #' + batch.prompt_number;
    leftDiv.appendChild(numberSpan);

    if (batch.user_prompt) {
        var previewDiv = document.createElement('div');
        previewDiv.style.fontSize = '0.75rem';
        previewDiv.style.color = 'var(--text-secondary)';
        previewDiv.style.whiteSpace = 'nowrap';
        previewDiv.style.overflow = 'hidden';
        previewDiv.style.textOverflow = 'ellipsis';
        previewDiv.style.marginTop = '0.125rem';

        var preview = batch.user_prompt.replace(/\n/g, ' ').trim();
        if (preview.length > 60) {
            preview = preview.substring(0, 57) + '...';
        }
        previewDiv.textContent = preview;
        previewDiv.title = batch.user_prompt.substring(0, 200);
        leftDiv.appendChild(previewDiv);
    }

    item.appendChild(leftDiv);

    // Right side: classification badge and activity count
    var rightDiv = document.createElement('div');
    rightDiv.style.display = 'flex';
    rightDiv.style.alignItems = 'center';
    rightDiv.style.gap = '0.5rem';
    rightDiv.style.flexShrink = '0';

    if (batch.classification) {
        var classColors = {
            'exploration': 'var(--info)',
            'implementation': 'var(--success)',
            'debugging': 'var(--warning)',
            'refactoring': 'var(--accent)'
        };
        var color = classColors[batch.classification] || 'var(--text-secondary)';
        var badge = document.createElement('span');
        badge.style.background = color + '22';
        badge.style.color = color;
        badge.style.padding = '0.125rem 0.375rem';
        badge.style.borderRadius = '3px';
        badge.style.fontSize = '0.65rem';
        badge.style.fontWeight = 'bold';
        badge.textContent = batch.classification;
        rightDiv.appendChild(badge);
    }

    if (batch.activity_count > 0) {
        var countSpan = document.createElement('span');
        countSpan.style.fontSize = '0.7rem';
        countSpan.style.color = 'var(--text-secondary)';
        countSpan.textContent = batch.activity_count + ' act.';
        rightDiv.appendChild(countSpan);
    }

    item.appendChild(rightDiv);

    return item;
}

// ============================================================================
// Activity Browser (SQLite activity tracking)
// ============================================================================

// Tool icons for activity display
var toolIcons = {
    'Bash': '&#x1F4BB;',     // laptop
    'Read': '&#x1F4D6;',     // book
    'Edit': '&#x270F;',      // pencil
    'Write': '&#x1F4DD;',    // memo
    'Grep': '&#x1F50D;',     // magnifying glass
    'Glob': '&#x1F4C1;',     // folder
    'Task': '&#x1F4CB;',     // clipboard
    'WebFetch': '&#x1F310;', // globe
    'WebSearch': '&#x1F50E;' // magnifying glass tilted right
};

function createSessionListItem(session) {
    var item = document.createElement('div');
    item.className = 'result-item';
    item.style.padding = '0.75rem';
    item.style.marginBottom = '0.5rem';
    item.style.cursor = 'pointer';
    item.dataset.sessionId = session.id;

    // Header with agent and status
    var header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'flex-start';
    header.style.marginBottom = '0.25rem';

    var agentSpan = document.createElement('span');
    agentSpan.style.fontWeight = 'bold';
    agentSpan.style.fontSize = '0.875rem';
    agentSpan.textContent = session.agent || 'Unknown Agent';

    var statusSpan = document.createElement('span');
    statusSpan.style.fontSize = '0.7rem';
    statusSpan.style.padding = '0.125rem 0.375rem';
    statusSpan.style.borderRadius = '4px';
    if (session.status === 'active') {
        statusSpan.style.background = 'var(--success)';
        statusSpan.style.color = 'white';
        statusSpan.textContent = 'ACTIVE';
    } else {
        statusSpan.style.background = 'var(--bg-tertiary)';
        statusSpan.style.color = 'var(--text-secondary)';
        statusSpan.textContent = session.status || 'completed';
    }

    header.appendChild(agentSpan);
    header.appendChild(statusSpan);

    // Session info row
    var infoDiv = document.createElement('div');
    infoDiv.style.fontSize = '0.75rem';
    infoDiv.style.color = 'var(--text-secondary)';
    infoDiv.style.marginBottom = '0.25rem';

    var startTime = '';
    if (session.started_at) {
        try {
            var dt = new Date(session.started_at);
            startTime = dt.toLocaleDateString() + ' ' + dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } catch (e) {
            startTime = session.started_at;
        }
    }

    var activityCount = session.activity_count || 0;
    var batchCount = session.prompt_batch_count || 0;
    infoDiv.textContent = startTime + ' | ' + activityCount + ' activities | ' + batchCount + ' prompts';

    // Summary if available
    var summaryDiv = null;
    if (session.summary) {
        summaryDiv = document.createElement('div');
        summaryDiv.style.fontSize = '0.8rem';
        summaryDiv.style.color = 'var(--text-primary)';
        summaryDiv.style.marginTop = '0.25rem';
        var summary = session.summary;
        if (summary.length > 100) {
            summary = summary.substring(0, 97) + '...';
        }
        summaryDiv.textContent = summary;
    }

    item.appendChild(header);
    item.appendChild(infoDiv);
    if (summaryDiv) {
        item.appendChild(summaryDiv);
    }

    // Click to view session details
    item.addEventListener('click', function () {
        viewSessionDetails(session.id);
    });

    return item;
}

function createActivityListItem(activity) {
    var item = document.createElement('div');
    item.className = 'result-item';
    item.style.padding = '0.5rem 0.75rem';
    item.style.marginBottom = '0.375rem';
    item.style.fontSize = '0.8rem';
    item.style.cursor = 'pointer';
    item.style.transition = 'background-color 0.15s ease';

    // Click handler to show details
    item.addEventListener('click', function() {
        showActivityDetail(activity);
    });

    // Hover effect
    item.addEventListener('mouseenter', function() {
        item.style.background = 'var(--bg-tertiary)';
    });
    item.addEventListener('mouseleave', function() {
        item.style.background = '';
    });

    // Header with tool name and status
    var header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'center';
    header.style.marginBottom = '0.25rem';

    var toolSpan = document.createElement('span');
    toolSpan.style.fontWeight = 'bold';
    var icon = toolIcons[activity.tool_name] || '&#x2699;';
    toolSpan.innerHTML = icon + ' ' + activity.tool_name;

    var timeSpan = document.createElement('span');
    timeSpan.style.fontSize = '0.7rem';
    timeSpan.style.color = 'var(--text-secondary)';
    if (activity.created_at) {
        try {
            var dt = new Date(activity.created_at);
            timeSpan.textContent = dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        } catch (e) {
            timeSpan.textContent = '';
        }
    }

    header.appendChild(toolSpan);
    header.appendChild(timeSpan);

    // Input/details summary
    var detailDiv = document.createElement('div');
    detailDiv.style.fontSize = '0.75rem';
    detailDiv.style.color = 'var(--text-secondary)';
    detailDiv.style.fontFamily = "'SF Mono', SFMono-Regular, Consolas, monospace";
    detailDiv.style.whiteSpace = 'nowrap';
    detailDiv.style.overflow = 'hidden';
    detailDiv.style.textOverflow = 'ellipsis';

    var detail = '';
    if (activity.file_path) {
        detail = activity.file_path;
    } else if (activity.tool_input) {
        if (activity.tool_name === 'Bash' && activity.tool_input.command) {
            detail = '$ ' + activity.tool_input.command;
        } else if (activity.tool_input.query) {
            detail = 'query: ' + activity.tool_input.query;
        } else if (activity.tool_input.pattern) {
            detail = 'pattern: ' + activity.tool_input.pattern;
        } else {
            detail = JSON.stringify(activity.tool_input).substring(0, 100);
        }
    }

    if (detail.length > 80) {
        detail = detail.substring(0, 77) + '...';
    }
    detailDiv.textContent = detail;
    detailDiv.title = detail; // Full text on hover

    // Error indicator
    if (!activity.success) {
        var errorDiv = document.createElement('div');
        errorDiv.style.fontSize = '0.7rem';
        errorDiv.style.color = 'var(--error)';
        errorDiv.style.marginTop = '0.25rem';
        errorDiv.textContent = '✗ ' + (activity.error_message || 'Error');
        item.appendChild(header);
        item.appendChild(detailDiv);
        item.appendChild(errorDiv);
    } else {
        item.appendChild(header);
        item.appendChild(detailDiv);
    }

    return item;
}

async function loadSessions() {
    var container = document.getElementById('sessions-list');
    var paginationEl = document.getElementById('sessions-pagination');

    // Guard against missing elements (e.g., tab not yet visible)
    if (!container || !paginationEl) {
        debug('loadSessions: DOM elements not ready');
        return;
    }

    // Show loading
    container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading sessions...</div>';

    try {
        var url = API_BASE + '/api/activity/sessions?limit=' + sessionsState.limit + '&offset=' + sessionsState.offset;
        if (sessionsState.statusFilter) {
            url += '&status=' + sessionsState.statusFilter;
        }

        var response = await fetch(url);
        if (!response.ok) {
            throw new Error('API returned ' + response.status);
        }
        var data = await response.json();

        if (!data) {
            throw new Error('Empty response from API');
        }

        sessionsState.total = data.total || 0;
        var sessions = data.sessions || [];

        // Clear container
        container.innerHTML = '';

        if (sessions.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.style.padding = '2rem';
            empty.style.textAlign = 'center';
            empty.innerHTML = '<div style="font-size: 2rem; margin-bottom: 0.5rem;">&#x1F4AD;</div>' +
                '<p style="color: var(--text-secondary);">No sessions found</p>' +
                '<p style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.5rem;">Sessions are recorded when using Claude Code with CI hooks enabled.</p>';
            container.appendChild(empty);
            paginationEl.style.display = 'none';
            return;
        }

        sessions.forEach(function (session) {
            container.appendChild(createSessionListItem(session));
        });

        // Update pagination
        var currentPage = Math.floor(sessionsState.offset / sessionsState.limit) + 1;
        var totalPages = Math.ceil(sessionsState.total / sessionsState.limit);

        document.getElementById('sessions-page-info').textContent =
            'Page ' + currentPage + ' of ' + totalPages + ' (' + sessionsState.total + ' total)';

        document.getElementById('sessions-prev-btn').disabled = sessionsState.offset === 0;
        document.getElementById('sessions-next-btn').disabled =
            sessionsState.offset + sessionsState.limit >= sessionsState.total;

        paginationEl.style.display = 'flex';

    } catch (error) {
        container.innerHTML = '<div class="empty-state" style="padding: 2rem; text-align: center;">' +
            '<p style="color: var(--error);">Failed to load sessions: ' + error.message + '</p></div>';
        paginationEl.style.display = 'none';
    }
}

async function viewSessionDetails(sessionId) {
    var detailCard = document.getElementById('session-detail-card');
    var detailContent = document.getElementById('session-detail-content');
    var activitiesCard = document.getElementById('activities-card');
    var toolFilter = document.getElementById('activities-tool-filter');

    // Show detail card
    detailCard.style.display = 'block';
    detailContent.innerHTML = '<div class="loading"><div class="spinner"></div>Loading session...</div>';

    try {
        var response = await fetch(API_BASE + '/api/activity/sessions/' + sessionId);
        if (!response.ok) {
            throw new Error('API returned ' + response.status);
        }
        var data = await response.json();

        var session = data.session;
        var stats = data.stats || {};

        // Populate tool filter dropdown dynamically from session stats
        if (toolFilter && stats.tool_counts) {
            // Clear existing options except "All Tools"
            toolFilter.innerHTML = '<option value="">All Tools</option>';
            // Add tools from this session, sorted by count
            var tools = Object.entries(stats.tool_counts).sort(function(a, b) { return b[1] - a[1]; });
            tools.forEach(function(entry) {
                var option = document.createElement('option');
                option.value = entry[0];
                option.textContent = entry[0] + ' (' + entry[1] + ')';
                toolFilter.appendChild(option);
            });
        }

        // Build detail content
        var content = document.createElement('div');

        // Session info
        var infoDiv = document.createElement('div');
        infoDiv.style.marginBottom = '0.75rem';

        var agentLine = document.createElement('div');
        agentLine.innerHTML = '<strong>Agent:</strong> ' + (session.agent || 'Unknown');
        infoDiv.appendChild(agentLine);

        var statusLine = document.createElement('div');
        statusLine.innerHTML = '<strong>Status:</strong> ' + (session.status || 'unknown');
        infoDiv.appendChild(statusLine);

        if (session.started_at) {
            var startLine = document.createElement('div');
            var dt = new Date(session.started_at);
            startLine.innerHTML = '<strong>Started:</strong> ' + dt.toLocaleString();
            infoDiv.appendChild(startLine);
        }

        if (session.ended_at) {
            var endLine = document.createElement('div');
            var endDt = new Date(session.ended_at);
            endLine.innerHTML = '<strong>Ended:</strong> ' + endDt.toLocaleString();
            infoDiv.appendChild(endLine);
        }

        content.appendChild(infoDiv);

        // Stats
        if (stats) {
            var statsDiv = document.createElement('div');
            statsDiv.style.background = 'var(--bg-tertiary)';
            statsDiv.style.padding = '0.5rem 0.75rem';
            statsDiv.style.borderRadius = '6px';
            statsDiv.style.fontSize = '0.8rem';
            statsDiv.style.marginBottom = '0.75rem';

            var statsText = [];
            if (stats.activity_count) statsText.push(stats.activity_count + ' activities');
            if (stats.files_touched) statsText.push(stats.files_touched + ' files');
            if (stats.prompt_batch_count) statsText.push(stats.prompt_batch_count + ' prompts');

            statsDiv.textContent = statsText.join(' | ') || 'No stats available';

            // Tool breakdown
            if (stats.tool_counts && Object.keys(stats.tool_counts).length > 0) {
                var toolsLine = document.createElement('div');
                toolsLine.style.marginTop = '0.25rem';
                toolsLine.style.fontSize = '0.75rem';
                toolsLine.style.color = 'var(--text-secondary)';
                var toolParts = [];
                for (var tool in stats.tool_counts) {
                    toolParts.push(tool + ': ' + stats.tool_counts[tool]);
                }
                toolsLine.textContent = 'Tools: ' + toolParts.join(', ');
                statsDiv.appendChild(toolsLine);
            }

            content.appendChild(statsDiv);
        }

        // Summary if available
        if (session.summary) {
            var summaryDiv = document.createElement('div');
            summaryDiv.style.background = 'var(--bg-secondary)';
            summaryDiv.style.padding = '0.5rem 0.75rem';
            summaryDiv.style.borderRadius = '6px';
            summaryDiv.style.fontSize = '0.8rem';
            summaryDiv.innerHTML = '<strong>Summary:</strong> ' + session.summary;
            content.appendChild(summaryDiv);
        }

        // Prompt Batches section
        var promptBatches = data.prompt_batches || [];
        if (promptBatches.length > 0) {
            var batchesSection = document.createElement('div');
            batchesSection.style.marginTop = '1rem';

            var batchesHeader = document.createElement('div');
            batchesHeader.style.fontWeight = 'bold';
            batchesHeader.style.marginBottom = '0.5rem';
            batchesHeader.style.fontSize = '0.85rem';
            batchesHeader.innerHTML = '&#x1F4AC; Prompts (' + promptBatches.length + ')';
            batchesSection.appendChild(batchesHeader);

            var batchesList = document.createElement('div');
            batchesList.style.maxHeight = '200px';
            batchesList.style.overflowY = 'auto';
            batchesList.style.border = '1px solid var(--border-color)';
            batchesList.style.borderRadius = '6px';
            batchesList.style.padding = '0.25rem';

            promptBatches.forEach(function(batch) {
                batchesList.appendChild(createPromptBatchListItem(batch));
            });

            batchesSection.appendChild(batchesList);
            content.appendChild(batchesSection);
        }

        detailContent.innerHTML = '';
        detailContent.appendChild(content);

        // Load activities for this session
        activitiesState.sessionId = sessionId;
        activitiesState.offset = 0;
        document.getElementById('activities-title').textContent = 'Session Activities';
        loadSessionActivities();
        activitiesCard.style.display = 'block';

    } catch (error) {
        detailContent.innerHTML = '<p style="color: var(--error);">Failed to load session: ' + error.message + '</p>';
    }
}

async function loadSessionActivities() {
    var container = document.getElementById('activities-list');
    var paginationEl = document.getElementById('activities-pagination');

    if (!activitiesState.sessionId) {
        container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 1rem;">Select a session to view activities.</p>';
        paginationEl.style.display = 'none';
        return;
    }

    container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading activities...</div>';

    try {
        var url = API_BASE + '/api/activity/sessions/' + activitiesState.sessionId + '/activities' +
            '?limit=' + activitiesState.limit + '&offset=' + activitiesState.offset;
        if (activitiesState.toolFilter) {
            url += '&tool_name=' + activitiesState.toolFilter;
        }

        var response = await fetch(url);
        var data = await response.json();

        activitiesState.total = data.total || 0;
        var activities = data.activities || [];

        container.innerHTML = '';

        if (activities.length === 0) {
            var empty = document.createElement('div');
            empty.style.textAlign = 'center';
            empty.style.padding = '1rem';
            empty.style.color = 'var(--text-secondary)';
            empty.textContent = 'No activities found for this session.';
            container.appendChild(empty);
            paginationEl.style.display = 'none';
            return;
        }

        activities.forEach(function (activity) {
            container.appendChild(createActivityListItem(activity));
        });

        // Update pagination
        var currentPage = Math.floor(activitiesState.offset / activitiesState.limit) + 1;
        var totalPages = Math.ceil(activitiesState.total / activitiesState.limit);

        document.getElementById('activities-page-info').textContent =
            'Page ' + currentPage + ' of ' + totalPages;

        document.getElementById('activities-prev-btn').disabled = activitiesState.offset === 0;
        document.getElementById('activities-next-btn').disabled =
            activitiesState.offset + activitiesState.limit >= activitiesState.total;

        paginationEl.style.display = 'flex';

    } catch (error) {
        container.innerHTML = '<p style="color: var(--error); text-align: center; padding: 1rem;">Failed to load activities: ' + error.message + '</p>';
        paginationEl.style.display = 'none';
    }
}

async function searchActivities() {
    var query = document.getElementById('activity-search-input').value.trim();
    if (!query) return;

    var container = document.getElementById('activities-list');
    var activitiesCard = document.getElementById('activities-card');
    var paginationEl = document.getElementById('activities-pagination');

    // Show activities card and update title
    activitiesCard.style.display = 'block';
    document.getElementById('activities-title').textContent = 'Search Results: "' + query + '"';

    container.innerHTML = '<div class="loading"><div class="spinner"></div>Searching...</div>';

    try {
        var url = API_BASE + '/api/activity/search?query=' + encodeURIComponent(query) + '&limit=50';

        var response = await fetch(url);
        var data = await response.json();

        var activities = data.activities || [];

        container.innerHTML = '';

        if (activities.length === 0) {
            var empty = document.createElement('div');
            empty.style.textAlign = 'center';
            empty.style.padding = '1rem';
            empty.style.color = 'var(--text-secondary)';
            empty.textContent = 'No activities found for "' + query + '"';
            container.appendChild(empty);
            paginationEl.style.display = 'none';
            return;
        }

        activities.forEach(function (activity) {
            container.appendChild(createActivityListItem(activity));
        });

        paginationEl.style.display = 'none'; // Search doesn't have pagination

    } catch (error) {
        container.innerHTML = '<p style="color: var(--error); text-align: center; padding: 1rem;">Search failed: ' + error.message + '</p>';
        paginationEl.style.display = 'none';
    }
}

function closeSessionDetail() {
    document.getElementById('session-detail-card').style.display = 'none';
    document.getElementById('activities-card').style.display = 'none';
    activitiesState.sessionId = null;
}

function sessionsNextPage() {
    if (sessionsState.offset + sessionsState.limit < sessionsState.total) {
        sessionsState.offset += sessionsState.limit;
        loadSessions();
    }
}

function sessionsPrevPage() {
    if (sessionsState.offset > 0) {
        sessionsState.offset = Math.max(0, sessionsState.offset - sessionsState.limit);
        loadSessions();
    }
}

function activitiesNextPage() {
    if (activitiesState.offset + activitiesState.limit < activitiesState.total) {
        activitiesState.offset += activitiesState.limit;
        loadSessionActivities();
    }
}

function activitiesPrevPage() {
    if (activitiesState.offset > 0) {
        activitiesState.offset = Math.max(0, activitiesState.offset - activitiesState.limit);
        loadSessionActivities();
    }
}

function sessionsFilterChanged() {
    var filter = document.getElementById('sessions-filter').value;
    sessionsState.statusFilter = filter || null;
    sessionsState.offset = 0;
    loadSessions();
}

function activitiesToolFilterChanged() {
    var filter = document.getElementById('activities-tool-filter').value;
    activitiesState.toolFilter = filter || null;
    activitiesState.offset = 0;
    loadSessionActivities();
}

// Rebuild index
async function rebuildIndex() {
    if (!confirm('This will rebuild the entire index. Continue?')) return;

    try {
        var response = await fetch(API_BASE + '/api/index/rebuild', { method: 'POST' });
        if (response.ok) {
            alert('Index rebuild started');
            fetchStatus();
        } else {
            var error = await response.json();
            alert('Failed to start rebuild: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to start rebuild: ' + error.message);
    }
}

// Fetch logs
async function fetchLogs() {
    try {
        var response = await fetch(API_BASE + '/api/logs?lines=100');
        var data = await response.json();
        document.getElementById('logs-content').textContent = data.content || 'No logs available';
        // Scroll to bottom
        var logsEl = document.getElementById('logs-content');
        logsEl.scrollTop = logsEl.scrollHeight;
    } catch (error) {
        document.getElementById('logs-content').textContent = 'Failed to fetch logs: ' + error.message;
    }
}

// Toggle logs visibility
var logsVisible = false;
function toggleLogs() {
    logsVisible = !logsVisible;
    document.getElementById('logs-section').style.display = logsVisible ? 'block' : 'none';
    document.getElementById('toggle-logs-btn').textContent = logsVisible ? 'Hide Logs' : 'Show Logs';
    if (logsVisible) fetchLogs();
}

// Configuration management
var knownModels = [];

async function loadModels(preserveSelection, savedModel) {
    var modelSelect = document.getElementById('config-model');
    var provider = document.getElementById('config-provider').value;
    var baseUrl = document.getElementById('config-base-url').value || 'http://localhost:11434';
    var currentSelection = modelSelect.value;
    debug('loadModels', { provider, baseUrl, preserveSelection, savedModel });

    // Show loading state
    modelSelect.innerHTML = '<option value="">Loading models...</option>';
    modelSelect.disabled = true;

    try {
        // Query the provider for available models
        var url = API_BASE + '/api/providers/models?provider=' + encodeURIComponent(provider) +
            '&base_url=' + encodeURIComponent(baseUrl);
        var response = await fetch(url);
        var data = await response.json();
        debug('loadModels response', data);

        modelSelect.innerHTML = '';

        if (data.success && data.models && data.models.length > 0) {
            knownModels = data.models;

            // Check if saved model is in the list
            var savedModelInList = savedModel && data.models.some(function (m) {
                return m.name === savedModel;
            });

            // Add placeholder if no model is configured
            if (!savedModel && !preserveSelection) {
                var placeholderOption = document.createElement('option');
                placeholderOption.value = '';
                placeholderOption.textContent = '-- Select a model --';
                modelSelect.appendChild(placeholderOption);
            }

            data.models.forEach(function (model) {
                var option = document.createElement('option');
                option.value = model.name;
                option.textContent = model.display_name + ' (' + model.dimensions + 'd)';
                modelSelect.appendChild(option);
            });

            // If saved model is not in list, add it as a custom option
            if (savedModel && !savedModelInList) {
                debug('Saved model not in list, adding as custom:', savedModel);
                var customOption = document.createElement('option');
                customOption.value = savedModel;
                customOption.textContent = savedModel + ' (configured)';
                modelSelect.insertBefore(customOption, modelSelect.firstChild);
            }

            // Set the selection
            if (savedModel) {
                modelSelect.value = savedModel;
            } else if (preserveSelection && currentSelection) {
                modelSelect.value = currentSelection;
            }
        } else {
            // No models from API - still add the saved model if we have one
            if (savedModel) {
                var savedOption = document.createElement('option');
                savedOption.value = savedModel;
                savedOption.textContent = savedModel + ' (configured)';
                modelSelect.appendChild(savedOption);
                modelSelect.value = savedModel;
            } else {
                modelSelect.innerHTML = '<option value="">No models found - check provider settings</option>';
            }
            var errorMsg = data.error || 'No embedding models available. Check that Ollama is running.';
            document.getElementById('config-message').style.display = 'block';
            document.getElementById('config-message').style.color = 'var(--warning)';
            document.getElementById('config-message').textContent = errorMsg;
        }
    } catch (error) {
        console.error('Failed to load models:', error);
        // Even on error, show the saved model if available
        modelSelect.innerHTML = '';
        if (savedModel) {
            var fallbackOption = document.createElement('option');
            fallbackOption.value = savedModel;
            fallbackOption.textContent = savedModel + ' (configured)';
            modelSelect.appendChild(fallbackOption);
            modelSelect.value = savedModel;
        } else {
            var errorOption = document.createElement('option');
            errorOption.value = '';
            errorOption.textContent = 'Failed to load models';
            modelSelect.appendChild(errorOption);
        }
    } finally {
        modelSelect.disabled = false;
    }
}

async function loadConfig() {
    try {
        // First, fetch the current config
        var response = await fetch(API_BASE + '/api/config');
        var data = await response.json();
        debug('loadConfig response', data);

        // Set provider and base URL BEFORE loading models
        // (loadModels depends on these form values)
        document.getElementById('config-provider').value = data.embedding.provider || 'ollama';
        document.getElementById('config-base-url').value = data.embedding.base_url || 'http://localhost:11434';

        // Set context/chunk fields (empty means auto-detect)
        document.getElementById('config-context-tokens').value = data.embedding.context_tokens || '';
        document.getElementById('config-max-chunk').value = data.embedding.max_chunk_chars || '';

        // Get saved model before loading models (may be null if not configured)
        var savedModel = data.embedding.model || null;

        // Now load models from the provider, passing the saved model
        // so it can be added to the list even if not available from API
        await loadModels(false, savedModel);

        updateConfigInfo(savedModel);

        // Enable/disable Save button based on whether context is configured
        var saveBtn = document.getElementById('save-config-btn');
        if (data.embedding.context_tokens && data.embedding.model) {
            saveBtn.disabled = false;
            saveBtn.title = '';
        } else if (data.embedding.model) {
            saveBtn.disabled = true;
            saveBtn.title = 'Click Discover to detect context window first';
            var msgEl = document.getElementById('config-message');
            msgEl.style.display = 'block';
            msgEl.style.color = 'var(--warning)';
            msgEl.textContent = 'Click Discover to detect context window for ' + data.embedding.model;
        } else {
            saveBtn.disabled = true;
            saveBtn.title = 'Select a model first';
        }

        // Load summarization config
        if (data.summarization) {
            debug('Loading summarization config');
            document.getElementById('sum-enabled').checked = data.summarization.enabled !== false;
            document.getElementById('sum-provider').value = data.summarization.provider || 'ollama';
            document.getElementById('sum-base-url').value = data.summarization.base_url || 'http://localhost:11434';
            document.getElementById('sum-context-tokens').value = data.summarization.context_tokens || '';

            // Pass the saved model to loadSumModels so it can be added if not in the list
            var savedSumModel = data.summarization.model || null;
            await loadSumModels(false, savedSumModel);

            // Enable/disable Save button based on whether context is configured
            var sumSaveBtn = document.getElementById('save-sum-btn');
            if (data.summarization.context_tokens && data.summarization.model) {
                sumSaveBtn.disabled = false;
                sumSaveBtn.title = '';
            } else if (data.summarization.model) {
                sumSaveBtn.disabled = true;
                sumSaveBtn.title = 'Click Discover to detect context window first';
                var sumMsgEl = document.getElementById('sum-message');
                sumMsgEl.style.display = 'block';
                sumMsgEl.style.color = 'var(--warning)';
                sumMsgEl.textContent = 'Click Discover to detect context window for ' + data.summarization.model;
            } else {
                sumSaveBtn.disabled = true;
                sumSaveBtn.title = 'Select a model first';
            }
        }
    } catch (error) {
        console.error('Failed to load config:', error);
    }
}

function updateConfigInfo(modelName) {
    var model = knownModels.find(function (m) { return m.name === modelName; });
    var infoEl = document.getElementById('config-info');

    // Clear existing content
    infoEl.textContent = '';

    if (model) {
        var sizeStr = model.size ? ' (' + model.size + ')' : '';

        // Build info using DOM methods for safety
        var strong = document.createElement('strong');
        strong.textContent = model.display_name;
        infoEl.appendChild(strong);
        infoEl.appendChild(document.createTextNode(sizeStr));
        infoEl.appendChild(document.createElement('br'));
        infoEl.appendChild(document.createTextNode('Dimensions: ' + model.dimensions));
        infoEl.appendChild(document.createElement('br'));
        var hint = document.createElement('span');
        hint.style.cssText = 'color: var(--text-secondary); font-size: 0.8rem;';
        hint.textContent = 'Use Discover to detect context window from API, or set manually.';
        infoEl.appendChild(hint);

        // Update placeholder hints in input fields with known defaults
        document.getElementById('config-context-tokens').placeholder = model.context_tokens || 'Auto (8192)';
        document.getElementById('config-max-chunk').placeholder = model.max_chunk_chars || 'Auto (6000)';
    } else {
        infoEl.appendChild(document.createTextNode('Custom model - dimensions will be auto-detected on test.'));
        infoEl.appendChild(document.createElement('br'));
        var hint = document.createElement('span');
        hint.style.cssText = 'color: var(--text-secondary); font-size: 0.8rem;';
        hint.textContent = 'Use Discover to detect context window from API.';
        infoEl.appendChild(hint);
        document.getElementById('config-context-tokens').placeholder = 'Auto (8192)';
        document.getElementById('config-max-chunk').placeholder = 'Auto (6000)';
    }
}

async function testConfig() {
    var config = {
        provider: document.getElementById('config-provider').value,
        model: document.getElementById('config-model').value,
        base_url: document.getElementById('config-base-url').value
    };

    var msgEl = document.getElementById('config-message');
    var testBtn = document.getElementById('test-config-btn');

    msgEl.style.display = 'block';
    msgEl.style.color = 'var(--warning)';
    msgEl.textContent = 'Testing connection to ' + config.provider + '...';
    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';

    try {
        var response = await fetch(API_BASE + '/api/config/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        var data = await response.json();

        if (data.success) {
            msgEl.style.color = 'var(--success)';
            msgEl.textContent = '✓ ' + data.message;
            // Return the full response data (includes dimensions)
            return data;
        } else {
            msgEl.style.color = 'var(--error)';
            msgEl.textContent = '✗ ' + data.error + (data.suggestion ? ' — ' + data.suggestion : '');
            return null;
        }
    } catch (error) {
        msgEl.style.color = 'var(--error)';
        msgEl.textContent = '✗ Connection test failed: ' + error.message;
        return null;
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
    }
}

async function saveConfig() {
    // Get context/chunk values (null if empty for auto-detect)
    var contextTokens = document.getElementById('config-context-tokens').value;
    var maxChunk = document.getElementById('config-max-chunk').value;
    var selectedModel = document.getElementById('config-model').value;

    // Look up dimensions from known models (discovered during model list load)
    var dimensions = null;
    var modelInfo = knownModels.find(function(m) { return m.name === selectedModel; });
    if (modelInfo && modelInfo.dimensions) {
        dimensions = modelInfo.dimensions;
        debug('Found dimensions from model discovery:', dimensions);
    }

    var config = {
        provider: document.getElementById('config-provider').value,
        model: selectedModel,
        base_url: document.getElementById('config-base-url').value,
        context_tokens: contextTokens ? parseInt(contextTokens) : null,
        max_chunk_chars: maxChunk ? parseInt(maxChunk) : null,
        dimensions: dimensions  // Include dimensions from model discovery
    };

    var msgEl = document.getElementById('config-message');

    // Always test the configuration first
    msgEl.style.display = 'block';
    msgEl.style.color = 'var(--warning)';
    msgEl.textContent = 'Testing configuration...';

    var testResult = await testConfig();
    if (!testResult) {
        // Test failed - don't save
        return;
    }

    // If dimensions weren't found in knownModels, use the test result
    if (!config.dimensions && testResult.dimensions) {
        config.dimensions = testResult.dimensions;
        debug('Using dimensions from test result:', config.dimensions);
    }

    try {
        // Save config to disk
        msgEl.textContent = 'Saving configuration...';
        var response = await fetch(API_BASE + '/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        var data = await response.json();

        // Apply changes (reload config and embedding chain)
        msgEl.textContent = 'Applying changes...';

        var restartResponse = await fetch(API_BASE + '/api/restart', {
            method: 'POST'
        });

        var restartData = await restartResponse.json();

        if (restartResponse.ok) {
            msgEl.style.color = 'var(--success)';
            // Show the detailed message from the server
            msgEl.textContent = restartData.message || 'Configuration saved!';

            // If indexing started, show info color
            if (restartData.indexing_started) {
                msgEl.style.color = 'var(--info, var(--primary))';
            }
            // If index was cleared but not re-indexing, show warning
            else if (restartData.index_cleared) {
                msgEl.style.color = 'var(--warning)';
            }

            // Refresh status to show new provider and indexing progress
            setTimeout(fetchStatus, 500);
        } else {
            msgEl.style.color = 'var(--error)';
            msgEl.textContent = 'Failed to apply: ' + (restartData.detail || 'Unknown error');
        }
    } catch (error) {
        msgEl.style.display = 'block';
        msgEl.style.color = 'var(--error)';
        msgEl.textContent = 'Failed to save: ' + error.message;
    }
}

// Model select change handler - clear context/chunk and require Discover
document.getElementById('config-model').addEventListener('change', function (e) {
    updateConfigInfo(e.target.value);
    // Clear context and chunk - user must click Discover
    document.getElementById('config-context-tokens').value = '';
    document.getElementById('config-max-chunk').value = '';
    document.getElementById('config-max-chunk').placeholder = 'Auto (click Discover)';
    // Disable Save until Discover is clicked
    var saveBtn = document.getElementById('save-config-btn');
    saveBtn.disabled = true;
    saveBtn.title = 'Click Discover to detect context window first';
    // Show hint
    var msgEl = document.getElementById('config-message');
    msgEl.style.display = 'block';
    msgEl.style.color = 'var(--warning)';
    msgEl.textContent = 'Click Discover to detect context window for ' + (e.target.value || 'selected model');
});

// Discover context tokens for embedding model
async function discoverEmbedContext() {
    var model = document.getElementById('config-model').value;
    var provider = document.getElementById('config-provider').value;
    var baseUrl = document.getElementById('config-base-url').value;

    if (!model) {
        var msgEl = document.getElementById('config-message');
        msgEl.style.display = 'block';
        msgEl.style.color = 'var(--warning)';
        msgEl.textContent = 'Please select a model first.';
        return;
    }

    var discoverBtn = document.getElementById('discover-embed-context-btn');
    var contextInput = document.getElementById('config-context-tokens');
    var msgEl = document.getElementById('config-message');

    discoverBtn.disabled = true;
    discoverBtn.textContent = 'Discovering...';
    msgEl.style.display = 'block';
    msgEl.style.color = 'var(--warning)';
    msgEl.textContent = 'Discovering context window for ' + model + '...';

    try {
        var response = await fetch(API_BASE + '/api/config/discover-context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: model,
                provider: provider,
                base_url: baseUrl
            })
        });

        var data = await response.json();

        if (data.success) {
            contextInput.value = data.context_tokens;
            // Auto-calculate and set max chunk based on new context
            var maxChunkInput = document.getElementById('config-max-chunk');
            var autoChunk = Math.floor(data.context_tokens * 0.75);
            maxChunkInput.value = autoChunk;
            maxChunkInput.placeholder = 'Auto (' + autoChunk.toLocaleString() + ')';
            // Enable Save button now that we have valid context
            var saveBtn = document.getElementById('save-config-btn');
            saveBtn.disabled = false;
            saveBtn.title = '';
            msgEl.style.color = 'var(--success)';
            msgEl.textContent = '✓ ' + data.message;
        } else {
            msgEl.style.color = 'var(--error)';
            msgEl.textContent = '✗ ' + data.error + (data.suggestion ? ' — ' + data.suggestion : '');
        }
    } catch (error) {
        msgEl.style.color = 'var(--error)';
        msgEl.textContent = '✗ Discovery failed: ' + error.message;
    } finally {
        discoverBtn.disabled = false;
        discoverBtn.textContent = 'Discover';
    }
}

// ============================================================================
// Summarization Configuration
// ============================================================================

var sumModels = [];

async function loadSumModels(preserveSelection, savedModel) {
    var modelSelect = document.getElementById('sum-model');
    var provider = document.getElementById('sum-provider').value;
    var baseUrl = document.getElementById('sum-base-url').value || 'http://localhost:11434';
    var currentSelection = modelSelect.value;
    debug('loadSumModels', { provider, baseUrl, preserveSelection, savedModel });

    // Clear existing options
    while (modelSelect.firstChild) {
        modelSelect.removeChild(modelSelect.firstChild);
    }
    var loadingOption = document.createElement('option');
    loadingOption.value = '';
    loadingOption.textContent = 'Loading models...';
    modelSelect.appendChild(loadingOption);
    modelSelect.disabled = true;

    try {
        var url = API_BASE + '/api/providers/summarization-models?provider=' + encodeURIComponent(provider) +
            '&base_url=' + encodeURIComponent(baseUrl);
        var response = await fetch(url);
        var data = await response.json();
        debug('loadSumModels response', data);

        // Clear again before populating
        while (modelSelect.firstChild) {
            modelSelect.removeChild(modelSelect.firstChild);
        }

        if (data.success && data.models && data.models.length > 0) {
            sumModels = data.models;

            // Check if saved model is in the list
            var savedModelInList = savedModel && data.models.some(function (m) {
                return m.id === savedModel;
            });

            // Add placeholder if no model is configured
            if (!savedModel && !preserveSelection) {
                var placeholderOption = document.createElement('option');
                placeholderOption.value = '';
                placeholderOption.textContent = '-- Select a model --';
                modelSelect.appendChild(placeholderOption);
            }

            data.models.forEach(function (model) {
                var option = document.createElement('option');
                option.value = model.id;
                var ctxStr = model.context_window ? ' (' + (model.context_window/1000).toFixed(0) + 'k ctx)' : '';
                option.textContent = model.name + ctxStr;
                modelSelect.appendChild(option);
            });

            // If saved model is not in list, add it as a custom option
            if (savedModel && !savedModelInList) {
                debug('Saved model not in list, adding as custom:', savedModel);
                var customOption = document.createElement('option');
                customOption.value = savedModel;
                customOption.textContent = savedModel + ' (configured)';
                modelSelect.insertBefore(customOption, modelSelect.firstChild);
            }

            // Set the selection
            if (savedModel) {
                modelSelect.value = savedModel;
            } else if (preserveSelection && currentSelection) {
                modelSelect.value = currentSelection;
            }
        } else {
            // No models from API - still add the saved model if we have one
            if (savedModel) {
                var savedOption = document.createElement('option');
                savedOption.value = savedModel;
                savedOption.textContent = savedModel + ' (configured)';
                modelSelect.appendChild(savedOption);
                modelSelect.value = savedModel;
            } else {
                var emptyOption = document.createElement('option');
                emptyOption.value = '';
                emptyOption.textContent = 'No models found - check provider';
                modelSelect.appendChild(emptyOption);
            }
            var msgEl = document.getElementById('sum-message');
            msgEl.style.display = 'block';
            msgEl.style.color = 'var(--warning)';
            msgEl.textContent = data.error || 'No LLM models available. Check that Ollama is running.';
        }
    } catch (error) {
        console.error('Failed to load summarization models:', error);
        while (modelSelect.firstChild) {
            modelSelect.removeChild(modelSelect.firstChild);
        }
        // Even on error, show the saved model if available
        if (savedModel) {
            var fallbackOption = document.createElement('option');
            fallbackOption.value = savedModel;
            fallbackOption.textContent = savedModel + ' (configured)';
            modelSelect.appendChild(fallbackOption);
            modelSelect.value = savedModel;
        } else {
            var errorOption = document.createElement('option');
            errorOption.value = '';
            errorOption.textContent = 'Failed to load models';
            modelSelect.appendChild(errorOption);
        }
    } finally {
        modelSelect.disabled = false;
    }
}

async function loadSumConfig() {
    try {
        var response = await fetch(API_BASE + '/api/config');
        var data = await response.json();

        if (data.summarization) {
            document.getElementById('sum-enabled').checked = data.summarization.enabled !== false;
            document.getElementById('sum-provider').value = data.summarization.provider || 'ollama';
            document.getElementById('sum-base-url').value = data.summarization.base_url || 'http://localhost:11434';
            document.getElementById('sum-context-tokens').value = data.summarization.context_tokens || '';

            var savedModel = data.summarization.model || null;
            await loadSumModels(false, savedModel);
        }
    } catch (error) {
        console.error('Failed to load summarization config:', error);
    }
}

async function testSumConfig() {
    var config = {
        provider: document.getElementById('sum-provider').value,
        model: document.getElementById('sum-model').value,
        base_url: document.getElementById('sum-base-url').value
    };

    var msgEl = document.getElementById('sum-message');
    var testBtn = document.getElementById('test-sum-btn');

    msgEl.style.display = 'block';
    msgEl.style.color = 'var(--warning)';
    msgEl.textContent = 'Testing summarization with ' + config.model + '...';
    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';

    try {
        var response = await fetch(API_BASE + '/api/config/test-summarization', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        var data = await response.json();

        if (data.success) {
            msgEl.style.color = 'var(--success)';
            var ctxStr = data.context_window ? ' (context: ' + (data.context_window/1000).toFixed(0) + 'k)' : '';
            msgEl.textContent = '✓ ' + data.message + ctxStr;
            return true;
        } else {
            msgEl.style.color = 'var(--error)';
            msgEl.textContent = '✗ ' + data.error + (data.suggestion ? ' — ' + data.suggestion : '');
            return false;
        }
    } catch (error) {
        msgEl.style.color = 'var(--error)';
        msgEl.textContent = '✗ Connection test failed: ' + error.message;
        return false;
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
    }
}

async function saveSumConfig() {
    var contextTokensVal = document.getElementById('sum-context-tokens').value;
    var config = {
        summarization: {
            enabled: document.getElementById('sum-enabled').checked,
            provider: document.getElementById('sum-provider').value,
            model: document.getElementById('sum-model').value,
            base_url: document.getElementById('sum-base-url').value,
            context_tokens: contextTokensVal ? parseInt(contextTokensVal) : null
        }
    };

    var msgEl = document.getElementById('sum-message');

    try {
        var response = await fetch(API_BASE + '/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        var data = await response.json();

        msgEl.style.display = 'block';
        if (data.status === 'updated') {
            msgEl.style.color = 'var(--success)';
            msgEl.textContent = '✓ Summarization configuration saved. Changes take effect immediately.';
        } else {
            msgEl.style.color = 'var(--error)';
            msgEl.textContent = '✗ Failed to save: ' + (data.message || 'Unknown error');
        }
    } catch (error) {
        msgEl.style.display = 'block';
        msgEl.style.color = 'var(--error)';
        msgEl.textContent = '✗ Failed to save configuration: ' + error.message;
    }
}

async function discoverSumContext() {
    var model = document.getElementById('sum-model').value;
    var provider = document.getElementById('sum-provider').value;
    var baseUrl = document.getElementById('sum-base-url').value;

    if (!model) {
        var msgEl = document.getElementById('sum-message');
        msgEl.style.display = 'block';
        msgEl.style.color = 'var(--warning)';
        msgEl.textContent = 'Please select a model first.';
        return;
    }

    var discoverBtn = document.getElementById('discover-sum-context-btn');
    var contextInput = document.getElementById('sum-context-tokens');
    var msgEl = document.getElementById('sum-message');

    discoverBtn.disabled = true;
    discoverBtn.textContent = 'Discovering...';
    msgEl.style.display = 'block';
    msgEl.style.color = 'var(--warning)';
    msgEl.textContent = 'Discovering context window for ' + model + '...';

    try {
        var response = await fetch(API_BASE + '/api/config/discover-context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: model,
                provider: provider,
                base_url: baseUrl
            })
        });

        var data = await response.json();

        if (data.success && data.context_tokens) {
            contextInput.value = data.context_tokens;
            // Enable Save button now that we have valid context
            var saveBtn = document.getElementById('save-sum-btn');
            saveBtn.disabled = false;
            saveBtn.title = '';
            msgEl.style.color = 'var(--success)';
            msgEl.textContent = '✓ Discovered context window: ' + data.context_tokens.toLocaleString() + ' tokens. Click Save to persist.';
        } else {
            msgEl.style.color = 'var(--warning)';
            msgEl.textContent = 'Could not discover context window. ' + (data.error || 'Set manually based on your model specs.');
        }
    } catch (error) {
        msgEl.style.color = 'var(--error)';
        msgEl.textContent = '✗ Discovery failed: ' + error.message;
    } finally {
        discoverBtn.disabled = false;
        discoverBtn.textContent = 'Discover';
    }
}

// Summarization event listeners

// Model change handler - clear context and require Discover
document.getElementById('sum-model').addEventListener('change', function (e) {
    // Clear context - user must click Discover
    document.getElementById('sum-context-tokens').value = '';
    // Disable Save until Discover is clicked
    var saveBtn = document.getElementById('save-sum-btn');
    saveBtn.disabled = true;
    saveBtn.title = 'Click Discover to detect context window first';
    // Show hint
    var msgEl = document.getElementById('sum-message');
    if (e.target.value) {
        msgEl.style.display = 'block';
        msgEl.style.color = 'var(--warning)';
        msgEl.textContent = 'Click Discover to detect context window for ' + e.target.value;
    }
});

document.getElementById('sum-provider').addEventListener('change', function () {
    loadSumModels(false);
});

var sumBaseUrlTimeout = null;
document.getElementById('sum-base-url').addEventListener('input', function () {
    clearTimeout(sumBaseUrlTimeout);
    sumBaseUrlTimeout = setTimeout(function () {
        loadSumModels(true);
    }, 500);
});

document.getElementById('refresh-sum-models-btn').addEventListener('click', function () {
    loadSumModels(true);
});

document.getElementById('test-sum-btn').addEventListener('click', testSumConfig);
document.getElementById('save-sum-btn').addEventListener('click', saveSumConfig);
document.getElementById('discover-sum-context-btn').addEventListener('click', discoverSumContext);

// ============================================================================
// Embedding Configuration Event Listeners
// ============================================================================

// Provider change -> reload models from new provider
document.getElementById('config-provider').addEventListener('change', function () {
    var currentModel = document.getElementById('config-model').value;
    loadModels(false, currentModel);
});

// Base URL change with debounce -> reload models
var baseUrlTimeout = null;
document.getElementById('config-base-url').addEventListener('input', function () {
    clearTimeout(baseUrlTimeout);
    baseUrlTimeout = setTimeout(function () {
        var currentModel = document.getElementById('config-model').value;
        loadModels(true, currentModel);  // Preserve selection if possible
    }, 500);  // 500ms debounce
});

// Context tokens change -> update max chunk placeholder with auto-calculated value
document.getElementById('config-context-tokens').addEventListener('input', function () {
    var contextTokens = parseInt(this.value);
    var maxChunkInput = document.getElementById('config-max-chunk');

    if (contextTokens && contextTokens > 0) {
        // Auto-calculate: 0.75 chars per token (conservative for code which tokenizes aggressively)
        var autoChunk = Math.floor(contextTokens * 0.75);
        maxChunkInput.placeholder = 'Auto (' + autoChunk.toLocaleString() + ')';
    } else {
        // Revert to model default or generic default
        var modelName = document.getElementById('config-model').value;
        var model = knownModels.find(function (m) { return m.name === modelName; });
        maxChunkInput.placeholder = (model && model.max_chunk_chars) || 'Auto (6000)';
    }
});

// Refresh models button
document.getElementById('refresh-models-btn').addEventListener('click', function () {
    var currentModel = document.getElementById('config-model').value;
    loadModels(true, currentModel);
});

// Event listeners
document.getElementById('search-btn').addEventListener('click', performSearch);
document.getElementById('search-input').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') performSearch();
});
document.getElementById('save-memory-btn').addEventListener('click', saveMemory);
document.getElementById('rebuild-btn').addEventListener('click', rebuildIndex);
document.getElementById('refresh-btn').addEventListener('click', fetchStatus);
document.getElementById('toggle-logs-btn').addEventListener('click', toggleLogs);
document.getElementById('refresh-logs-btn').addEventListener('click', fetchLogs);
document.getElementById('save-config-btn').addEventListener('click', saveConfig);
document.getElementById('test-config-btn').addEventListener('click', testConfig);
document.getElementById('discover-embed-context-btn').addEventListener('click', discoverEmbedContext);

// Memories browser event listeners
document.getElementById('memories-filter').addEventListener('change', memoriesFilterChanged);
document.getElementById('refresh-memories-btn').addEventListener('click', loadMemories);
document.getElementById('reprocess-memories-btn').addEventListener('click', reprocessMemories);
document.getElementById('memories-prev-btn').addEventListener('click', memoriesPrevPage);
document.getElementById('memories-next-btn').addEventListener('click', memoriesNextPage);

// Activity browser event listeners
document.getElementById('sessions-filter').addEventListener('change', sessionsFilterChanged);
document.getElementById('refresh-sessions-btn').addEventListener('click', loadSessions);
document.getElementById('sessions-prev-btn').addEventListener('click', sessionsPrevPage);
document.getElementById('sessions-next-btn').addEventListener('click', sessionsNextPage);
document.getElementById('close-session-detail-btn').addEventListener('click', closeSessionDetail);
document.getElementById('activities-tool-filter').addEventListener('change', activitiesToolFilterChanged);
document.getElementById('activities-prev-btn').addEventListener('click', activitiesPrevPage);
document.getElementById('activities-next-btn').addEventListener('click', activitiesNextPage);
document.getElementById('activity-search-btn').addEventListener('click', searchActivities);
document.getElementById('activity-search-input').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') searchActivities();
});

// Initial load
fetchStatus();
setInterval(fetchStatus, 10000);
