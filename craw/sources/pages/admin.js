let currentPage = 1;
let totalPages = 1;
let deleteTargetId = null;

async function fetchApi(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.message || 'Lỗi');
  return data;
}

async function loadStats() {
  try {
    const s = await fetchApi('/api/stats');
    document.getElementById('stat-total').textContent = s.total_documents.toLocaleString();
    document.getElementById('stat-schools').textContent = (s.school_list || []).join(', ') || '-';
    const sel = document.getElementById('filter-school');
    const opts = sel.querySelectorAll('option:not(:first-child)');
    opts.forEach(o => o.remove());
    (s.school_list || []).forEach(sc => {
      const opt = document.createElement('option');
      opt.value = sc;
      opt.textContent = sc;
      sel.appendChild(opt);
    });
  } catch (e) {
    document.getElementById('stat-total').textContent = 'Lỗi';
  }
}

async function loadDocuments(page = 1) {
  currentPage = page;
  const search = document.getElementById('search').value.trim();
  const school = document.getElementById('filter-school').value;
  const file = document.getElementById('filter-file').value.trim();
  const params = new URLSearchParams({ page, limit: 20 });
  if (search) params.set('search', search);
  if (school) params.set('school', school);
  if (file) params.set('source_file', file);

  document.getElementById('doc-list').innerHTML = '<tr><td colspan="6" class="loading">Đang tải...</td></tr>';
  try {
    const data = await fetchApi('/api/documents?' + params);
    totalPages = data.total_pages || 1;
    renderTable(data.documents);
    renderPagination(data);
  } catch (e) {
    document.getElementById('doc-list').innerHTML = '<tr><td colspan="6" class="error">' + e.message + '</td></tr>';
  }
}

function renderTable(docs) {
  const tbody = document.getElementById('doc-list');
  if (!docs || docs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">Không có dữ liệu</td></tr>';
    return;
  }
  tbody.innerHTML = docs.map(d => `
    <tr>
      <td><code style="font-size:0.75rem">${(d._id || '').slice(-8)}</code></td>
      <td>${d.school || '-'}</td>
      <td title="${(d.source_file || '') + ' ' + (d.source_title || '')}">
        <div style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${d.source_file || '-'}</div>
      </td>
      <td><div class="content-preview" title="${(d.content || '').replace(/"/g, '&quot;')}">${(d.content || '').slice(0, 80)}...</div></td>
      <td><div class="tag-list">${(d.tags || []).slice(0,3).map(t=>'<span class="tag">'+t+'</span>').join('')}</div></td>
      <td class="actions">
        <button class="btn btn-ghost" onclick="openEditModal('${d._id}')">Sửa</button>
        <button class="btn btn-danger" onclick="openDeleteModal('${d._id}')">Xóa</button>
      </td>
    </tr>
  `).join('');
}

function renderPagination(data) {
  const div = document.getElementById('pagination');
  if (totalPages <= 1) { div.innerHTML = ''; return; }
  let html = `<button class="btn btn-ghost" ${currentPage <= 1 ? 'disabled' : ''} onclick="loadDocuments(${currentPage - 1})">←</button>`;
  html += `<span class="page-info">Trang ${currentPage} / ${totalPages} (${data.total} bản ghi)</span>`;
  html += `<button class="btn btn-ghost" ${currentPage >= totalPages ? 'disabled' : ''} onclick="loadDocuments(${currentPage + 1})">→</button>`;
  div.innerHTML = html;
}

function openEditModal(id) {
  document.getElementById('modal-title').textContent = 'Chỉnh sửa document';
  document.getElementById('modal-save-btn').textContent = 'Lưu';
  document.getElementById('edit-id').value = id;
  document.getElementById('modal-error').textContent = '';
  fetchApi('/api/documents/' + id).then(d => {
    document.getElementById('edit-school').value = d.school || '';
    document.getElementById('edit-source-file').value = d.source_file || '';
    document.getElementById('edit-source-url').value = d.source_url || '';
    document.getElementById('edit-source-title').value = d.source_title || '';
    document.getElementById('edit-content').value = d.content || '';
    document.getElementById('edit-tags').value = (d.tags || []).join(', ');
    document.getElementById('edit-chunk-id').value = d.chunk_id ?? '';
    document.getElementById('edit-total-chunks').value = d.total_chunks ?? '';
    document.getElementById('modal-overlay').classList.remove('hidden');
  }).catch(e => alert(e.message));
}

function openCreateModal() {
  document.getElementById('modal-title').textContent = 'Thêm document mới';
  document.getElementById('modal-save-btn').textContent = 'Tạo';
  document.getElementById('edit-id').value = '';
  document.getElementById('edit-school').value = '';
  document.getElementById('edit-source-file').value = '';
  document.getElementById('edit-source-url').value = '';
  document.getElementById('edit-source-title').value = '';
  document.getElementById('edit-content').value = '';
  document.getElementById('edit-tags').value = '';
  document.getElementById('edit-chunk-id').value = '';
  document.getElementById('edit-total-chunks').value = '';
  document.getElementById('modal-error').textContent = '';
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

async function saveDocument() {
  const id = document.getElementById('edit-id').value;
  const tagsStr = document.getElementById('edit-tags').value.trim();
  const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
  const payload = {
    school: document.getElementById('edit-school').value || null,
    source_file: document.getElementById('edit-source-file').value || null,
    source_url: document.getElementById('edit-source-url').value || null,
    source_title: document.getElementById('edit-source-title').value || null,
    content: document.getElementById('edit-content').value || null,
    tags,
    chunk_id: parseInt(document.getElementById('edit-chunk-id').value) || null,
    total_chunks: parseInt(document.getElementById('edit-total-chunks').value) || null,
  };

  const errEl = document.getElementById('modal-error');
  try {
    if (id) {
      const update = Object.fromEntries(Object.entries(payload).filter(([,v]) => v != null));
      await fetchApi('/api/documents/' + id, {
        method: 'PUT',
        body: JSON.stringify(update)
      });
    } else {
      if (!payload.content) throw new Error('Nội dung bắt buộc');
      await fetchApi('/api/documents', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
    }
    closeModal();
    loadDocuments(currentPage);
    loadStats();
  } catch (e) {
    errEl.textContent = e.message;
  }
}

function openDeleteModal(id) {
  deleteTargetId = id;
  document.getElementById('delete-modal').classList.remove('hidden');
}

function closeDeleteModal() {
  deleteTargetId = null;
  document.getElementById('delete-modal').classList.add('hidden');
}

async function confirmDelete() {
  if (!deleteTargetId) return;
  try {
    await fetchApi('/api/documents/' + deleteTargetId, { method: 'DELETE' });
    closeDeleteModal();
    loadDocuments(currentPage);
    loadStats();
  } catch (e) {
    alert(e.message);
  }
}

document.getElementById('search').addEventListener('keypress', e => {
  if (e.key === 'Enter') loadDocuments(1);
});

loadStats();
loadDocuments(1);
