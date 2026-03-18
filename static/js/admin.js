const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]').content;

let currentCategoryId = null;

// ─── Helpers ───
async function api(url, options = {}) {
    const headers = { "X-CSRFToken": CSRF_TOKEN, ...options.headers };
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${resp.status}`);
    }
    return resp.json();
}

function showModal(id) {
    document.getElementById(id).style.display = "flex";
}
function hideModal(id) {
    document.getElementById(id).style.display = "none";
}

// ─── Categories ───
async function loadCategories() {
    const cats = await api("/api/categories");
    const list = document.getElementById("admin-category-list");
    if (cats.length === 0) {
        list.innerHTML = '<p class="empty-state">Chưa có danh mục nào</p>';
        return;
    }
    list.innerHTML = cats
        .map(
            (c) => `
        <div class="sidebar-item ${c.id === currentCategoryId ? "active" : ""}"
             data-id="${c.id}">
            <span class="sidebar-item-text">${c.icon} ${c.name}</span>
            <span class="sidebar-item-count">${c.pdf_count}</span>
            <div class="sidebar-item-actions">
                <button class="btn-icon" title="Lên" onclick="moveCategory(${c.id}, -1, event)">▲</button>
                <button class="btn-icon" title="Xuống" onclick="moveCategory(${c.id}, 1, event)">▼</button>
                <button class="btn-icon" title="Sửa" onclick="editCategory(${c.id}, event)">✏️</button>
                <button class="btn-icon btn-icon-danger" title="Xóa" onclick="deleteCategory(${c.id}, event)">🗑️</button>
            </div>
        </div>`
        )
        .join("");

    // Click to select
    list.querySelectorAll(".sidebar-item").forEach((el) => {
        el.addEventListener("click", () => {
            currentCategoryId = parseInt(el.dataset.id);
            loadCategories();
            loadPdfs(currentCategoryId);
        });
    });
}

async function moveCategory(id, direction, event) {
    event.stopPropagation();
    const cats = await api("/api/categories");
    const idx = cats.findIndex((c) => c.id === id);
    const swapIdx = idx + direction;
    if (swapIdx < 0 || swapIdx >= cats.length) return;

    // Swap sort_order
    await api(`/admin/categories/${cats[idx].id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: cats[swapIdx].sort_order }),
    });
    await api(`/admin/categories/${cats[swapIdx].id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: cats[idx].sort_order }),
    });
    loadCategories();
}

async function editCategory(id, event) {
    event.stopPropagation();
    const cats = await api("/api/categories");
    const cat = cats.find((c) => c.id === id);
    if (!cat) return;

    document.getElementById("category-modal-title").textContent = "Sửa danh mục";
    document.getElementById("cat-name").value = cat.name;
    document.getElementById("cat-icon").value = cat.icon;
    document.getElementById("cat-id").value = id;
    showModal("category-modal");
}

async function deleteCategory(id, event) {
    event.stopPropagation();
    if (!confirm("Bạn có chắc muốn xóa danh mục này?")) return;
    try {
        await api(`/admin/categories/${id}`, { method: "DELETE" });
        if (currentCategoryId === id) {
            currentCategoryId = null;
            document.getElementById("admin-content").innerHTML =
                '<p class="empty-state">Chọn danh mục để quản lý</p>';
        }
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
}

// ─── Add/Edit Category Form ───
document.getElementById("btn-add-category").addEventListener("click", () => {
    document.getElementById("category-modal-title").textContent = "Thêm danh mục";
    document.getElementById("cat-name").value = "";
    document.getElementById("cat-icon").value = "📄";
    document.getElementById("cat-id").value = "";
    showModal("category-modal");
});

document.getElementById("btn-cancel-category").addEventListener("click", () => {
    hideModal("category-modal");
});

document.getElementById("category-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("cat-name").value.trim();
    const icon = document.getElementById("cat-icon").value.trim();
    const id = document.getElementById("cat-id").value;

    try {
        if (id) {
            await api(`/admin/categories/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, icon }),
            });
        } else {
            await api("/admin/categories", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, icon }),
            });
        }
        hideModal("category-modal");
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
});

// ─── PDFs ───
async function loadPdfs(categoryId) {
    const cats = await api("/api/categories");
    const cat = cats.find((c) => c.id === categoryId);
    if (!cat) return;

    const pdfs = await api(`/api/categories/${categoryId}/pdfs`);
    const content = document.getElementById("admin-content");

    let html = `
        <div class="admin-content-header">
            <h2>${cat.icon} ${cat.name} (${pdfs.length} file)</h2>
            <button class="btn btn-primary btn-sm" onclick="openUploadModal(${categoryId})">+ Upload PDF</button>
        </div>
    `;

    if (pdfs.length === 0) {
        html += '<p class="empty-state">Chưa có tài liệu nào trong danh mục này.</p>';
    } else {
        html += pdfs
            .map(
                (p) => `
            <div class="pdf-item">
                <div class="pdf-item-info">
                    <span class="pdf-item-title">📄 ${p.title}</span>
                    <span class="pdf-item-meta">${formatDate(p.uploaded_at)} · ${formatSize(p.file_size)}</span>
                </div>
                <div class="pdf-item-actions">
                    <a href="/pdf/${p.id}" target="_blank" class="btn btn-sm">Xem</a>
                    <button class="btn btn-sm btn-danger" onclick="deletePdf(${p.id})">Xóa</button>
                </div>
            </div>`
            )
            .join("");
    }

    content.innerHTML = html;
}

async function deletePdf(id) {
    if (!confirm("Bạn có chắc muốn xóa tài liệu này?")) return;
    try {
        await api(`/admin/pdfs/${id}`, { method: "DELETE" });
        loadPdfs(currentCategoryId);
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
}

// ─── Upload Modal ───
function openUploadModal(categoryId) {
    document.getElementById("upload-category-id").value = categoryId;
    document.getElementById("pdf-title").value = "";
    document.getElementById("pdf-file").value = "";
    showModal("upload-modal");
}

document.getElementById("btn-cancel-upload").addEventListener("click", () => {
    hideModal("upload-modal");
});

document.getElementById("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("pdf-title").value.trim();
    const file = document.getElementById("pdf-file").files[0];
    const categoryId = document.getElementById("upload-category-id").value;

    if (!title || !file) return;

    const formData = new FormData();
    formData.append("title", title);
    formData.append("file", file);
    formData.append("category_id", categoryId);

    try {
        await fetch("/admin/pdfs", {
            method: "POST",
            headers: { "X-CSRFToken": CSRF_TOKEN },
            body: formData,
        }).then((r) => {
            if (!r.ok) return r.json().then((d) => Promise.reject(new Error(d.error)));
            return r.json();
        });
        hideModal("upload-modal");
        loadPdfs(parseInt(categoryId));
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
});

// ─── Helpers ───
function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("vi-VN");
}
function formatSize(bytes) {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// ─── Init ───
loadCategories();
