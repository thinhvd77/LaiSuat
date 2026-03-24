const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]').content;

let currentCategoryId = null;
let expandedParents = new Set();

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

// ─── Mobile Sidebar ───
const adminSidebarToggle = document.getElementById("admin-sidebar-toggle");
const adminSidebar = document.getElementById("admin-sidebar");
const adminOverlay = document.getElementById("admin-sidebar-overlay");

function openAdminSidebar() {
    adminSidebar.classList.add("open");
    adminOverlay.classList.add("active");
}
function closeAdminSidebar() {
    adminSidebar.classList.remove("open");
    adminOverlay.classList.remove("active");
}

if (adminSidebarToggle) adminSidebarToggle.addEventListener("click", openAdminSidebar);
if (adminOverlay) adminOverlay.addEventListener("click", closeAdminSidebar);

// ─── Recursive Category Search ───
function findCategoryById(parents, id) {
    for (const p of parents) {
        if (p.id === id) return p;
        if (p.children) {
            for (const c of p.children) {
                if (c.id === id) return c;
                if (c.children) {
                    const found = c.children.find((gc) => gc.id === id);
                    if (found) return found;
                }
            }
        }
    }
    return null;
}

function countPdfs(cat) {
    if (cat.is_leaf) return cat.pdf_count || 0;
    if (!cat.children) return 0;
    return cat.children.reduce((sum, c) => sum + countPdfs(c), 0);
}

// ─── Categories (Accordion) ───
let categoriesData = []; // cache for modal dropdown

async function loadCategories() {
    const parents = await api("/api/categories");
    categoriesData = parents;
    const list = document.getElementById("admin-category-list");

    if (parents.length === 0) {
        list.innerHTML = `<p class="empty-state">
            <span class="empty-state-icon">📂</span>
            Chưa có danh mục nào
        </p>`;
        return;
    }

    // Auto-expand: find which root and L1 contain the selected category
    if (expandedParents.size === 0) {
        let found = false;
        for (const p of parents) {
            if (p.children) {
                for (const c of p.children) {
                    if (c.id === currentCategoryId) {
                        expandedParents.add(p.id);
                        found = true;
                        break;
                    }
                    if (c.children) {
                        for (const gc of c.children) {
                            if (gc.id === currentCategoryId) {
                                expandedParents.add(p.id);
                                expandedParents.add(c.id);
                                found = true;
                                break;
                            }
                        }
                    }
                    if (found) break;
                }
            }
            if (found) break;
        }
        if (!found && parents.length > 0) expandedParents.add(parents[0].id);
    }

    list.innerHTML = parents
        .map((p) => {
            const isExpanded = expandedParents.has(p.id);

            const childrenHtml = (p.children || [])
                .map((c) => {
                    if (c.is_leaf) {
                        // L1 leaf — clickable item with edit/delete + optional add
                        return `
                        <div class="sidebar-item ${c.id === currentCategoryId ? "active" : ""}"
                             data-id="${c.id}">
                            <span class="sidebar-item-text">${c.name}</span>
                            <span class="sidebar-item-count">${c.pdf_count}</span>
                            <div class="sidebar-item-actions">
                                ${c.can_have_children ? `<button class="btn-icon btn-icon-add" title="Thêm danh mục con" onclick="openAddCategoryForParent(${c.id}, event)">+</button>` : ""}
                                <button class="btn-icon" title="Sửa" onclick="editCategory(${c.id}, event)">✏️</button>
                                <button class="btn-icon btn-icon-danger" title="Xóa" onclick="deleteCategory(${c.id}, event)">🗑️</button>
                            </div>
                        </div>`;
                    } else {
                        // L1 with children — sub-accordion
                        const isSubExpanded = expandedParents.has(c.id);
                        const grandchildrenHtml = (c.children || [])
                            .map(
                                (gc) => `
                            <div class="sidebar-item ${gc.id === currentCategoryId ? "active" : ""}"
                                 data-id="${gc.id}">
                                <span class="sidebar-item-text">${gc.name}</span>
                                <span class="sidebar-item-count">${gc.pdf_count}</span>
                                <div class="sidebar-item-actions">
                                    <button class="btn-icon" title="Sửa" onclick="editCategory(${gc.id}, event)">✏️</button>
                                    <button class="btn-icon btn-icon-danger" title="Xóa" onclick="deleteCategory(${gc.id}, event)">🗑️</button>
                                </div>
                            </div>`
                            )
                            .join("");

                        return `
                        <div class="sidebar-subgroup ${isSubExpanded ? "expanded" : ""}">
                            <div class="sidebar-subgroup-header" data-subgroup-id="${c.id}">
                                <span class="sidebar-subgroup-name">${c.name}</span>
                                <span class="sidebar-subgroup-meta">
                                    <button class="btn-icon" title="Sửa" onclick="editCategory(${c.id}, event)">✏️</button>
                                    <button class="btn-icon btn-icon-danger" title="Xóa" onclick="deleteCategory(${c.id}, event)">🗑️</button>
                                    ${c.can_have_children ? `<button class="btn-icon btn-icon-add" title="Thêm danh mục con" onclick="openAddCategoryForParent(${c.id}, event)">+</button>` : ""}
                                    <svg class="sidebar-subgroup-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                        <polyline points="6 9 12 15 18 9"></polyline>
                                    </svg>
                                </span>
                            </div>
                            <div class="sidebar-subgroup-children">
                                ${grandchildrenHtml || '<p class="sidebar-empty">Chưa có danh mục con</p>'}
                            </div>
                        </div>`;
                    }
                })
                .join("");

            return `
            <div class="sidebar-group ${isExpanded ? "expanded" : ""}">
                <div class="sidebar-group-header" data-parent-id="${p.id}">
                    <span class="sidebar-group-name">${p.name}</span>
                    <span class="sidebar-group-meta">
                        <button class="btn-icon btn-icon-add" title="Thêm danh mục con" onclick="openAddCategoryForParent(${p.id}, event)">+</button>
                        <svg class="sidebar-group-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </span>
                </div>
                <div class="sidebar-group-children">
                    ${childrenHtml || '<p class="sidebar-empty">Chưa có danh mục con</p>'}
                </div>
            </div>`;
        })
        .join("");

    // Root accordion toggle (DOM-only, skip if clicking buttons)
    list.querySelectorAll(".sidebar-group-header").forEach((el) => {
        el.addEventListener("click", (e) => {
            if (e.target.closest(".btn-icon-add")) return;
            const parentId = parseInt(el.dataset.parentId);
            const group = el.closest(".sidebar-group");
            if (expandedParents.has(parentId)) {
                expandedParents.delete(parentId);
                group.classList.remove("expanded");
            } else {
                expandedParents.add(parentId);
                group.classList.add("expanded");
            }
        });
    });

    // Sub-accordion toggle (DOM-only, skip if clicking buttons)
    list.querySelectorAll(".sidebar-subgroup-header").forEach((el) => {
        el.addEventListener("click", (e) => {
            if (e.target.closest(".btn-icon") || e.target.closest(".btn-icon-add")) return;
            const subId = parseInt(el.dataset.subgroupId);
            const subgroup = el.closest(".sidebar-subgroup");
            if (expandedParents.has(subId)) {
                expandedParents.delete(subId);
                subgroup.classList.remove("expanded");
            } else {
                expandedParents.add(subId);
                subgroup.classList.add("expanded");
            }
        });
    });

    // Leaf item click → load PDFs
    list.querySelectorAll(".sidebar-item").forEach((el) => {
        el.addEventListener("click", () => {
            currentCategoryId = parseInt(el.dataset.id);
            loadCategories();
            loadPdfs(currentCategoryId);
            closeAdminSidebar();
        });
    });
}

// Open add category modal pre-filled with parent
function openAddCategoryForParent(parentId, event) {
    event.stopPropagation();
    document.getElementById("category-modal-title").textContent = "Thêm danh mục";
    document.getElementById("cat-name").value = "";
    document.getElementById("cat-id").value = "";
    document.getElementById("cat-parent-id").value = parentId;
    // Show file section for new categories
    document.getElementById("cat-file-section").style.display = "";
    document.getElementById("cat-file").value = "";
    document.getElementById("cat-pdf-title").value = "";
    document.getElementById("cat-pdf-title-group").style.display = "none";
    // Update parent dropdown
    _populateParentDropdown(parentId);
    showModal("category-modal");
}

function _populateParentDropdown(selectedParentId) {
    const select = document.getElementById("cat-parent-id");
    let html = "";
    for (const p of categoriesData) {
        html += `<optgroup label="${p.name}">`;
        // Root itself as an option
        html += `<option value="${p.id}" ${p.id === selectedParentId ? "selected" : ""}>${p.name}</option>`;
        // L1 children that can have children
        if (p.children) {
            for (const c of p.children) {
                if (c.can_have_children) {
                    html += `<option value="${c.id}" ${c.id === selectedParentId ? "selected" : ""}>— ${c.name}</option>`;
                }
            }
        }
        html += `</optgroup>`;
    }
    select.innerHTML = html;
}

async function editCategory(id, event) {
    event.stopPropagation();
    const cat = findCategoryById(categoriesData, id);
    if (!cat) return;

    document.getElementById("category-modal-title").textContent = "Sửa danh mục";
    document.getElementById("cat-name").value = cat.name;
    document.getElementById("cat-id").value = id;
    // Hide file section and parent dropdown when editing
    document.getElementById("cat-file-section").style.display = "none";
    document.getElementById("cat-parent-id").closest(".form-group").style.display = "none";
    showModal("category-modal");
}

async function deleteCategory(id, event) {
    event.stopPropagation();
    if (!confirm("Bạn có chắc muốn xóa danh mục này?")) return;
    try {
        await api(`/admin/categories/${id}`, { method: "DELETE" });
        if (currentCategoryId === id) {
            currentCategoryId = null;
            document.getElementById("admin-content").innerHTML = `<p class="empty-state">
                <span class="empty-state-icon">📂</span>
                Chọn danh mục để quản lý
            </p>`;
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
    document.getElementById("cat-id").value = "";
    // Show parent dropdown and file section
    document.getElementById("cat-parent-id").closest(".form-group").style.display = "";
    document.getElementById("cat-file-section").style.display = "";
    document.getElementById("cat-file").value = "";
    document.getElementById("cat-pdf-title").value = "";
    document.getElementById("cat-pdf-title-group").style.display = "none";
    // Populate parent dropdown (select first)
    _populateParentDropdown(categoriesData.length > 0 ? categoriesData[0].id : null);
    showModal("category-modal");
});

// Show/hide PDF title field when file is selected
document.getElementById("cat-file").addEventListener("change", (e) => {
    const titleGroup = document.getElementById("cat-pdf-title-group");
    if (e.target.files.length > 0) {
        titleGroup.style.display = "";
    } else {
        titleGroup.style.display = "none";
    }
});

document.getElementById("btn-cancel-category").addEventListener("click", () => {
    hideModal("category-modal");
    // Reset hidden elements
    document.getElementById("cat-parent-id").closest(".form-group").style.display = "";
});

document.getElementById("category-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("cat-name").value.trim();
    const id = document.getElementById("cat-id").value;

    try {
        if (id) {
            // Edit: JSON request (name only)
            await api(`/admin/categories/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name }),
            });
        } else {
            // Create: FormData (name + parent_id + optional file)
            const parentId = document.getElementById("cat-parent-id").value;
            const formData = new FormData();
            formData.append("name", name);
            formData.append("parent_id", parentId);

            const file = document.getElementById("cat-file").files[0];
            if (file) {
                formData.append("file", file);
                const pdfTitle = document.getElementById("cat-pdf-title").value.trim();
                if (pdfTitle) {
                    formData.append("pdf_title", pdfTitle);
                }
            }

            await fetch("/admin/categories", {
                method: "POST",
                headers: { "X-CSRFToken": CSRF_TOKEN },
                body: formData,
            }).then((r) => {
                if (!r.ok) return r.json().then((d) => Promise.reject(new Error(d.error)));
                return r.json();
            });
        }
        hideModal("category-modal");
        // Reset hidden elements
        document.getElementById("cat-parent-id").closest(".form-group").style.display = "";
        loadCategories();
        if (currentCategoryId) loadPdfs(currentCategoryId);
    } catch (e) {
        alert(e.message);
    }
});

// ─── PDFs ───
async function loadPdfs(categoryId) {
    const catObj = findCategoryById(categoriesData, categoryId);

    const pdfs = await api(`/api/categories/${categoryId}/pdfs`);
    const content = document.getElementById("admin-content");

    const catName = catObj ? catObj.name : "Danh mục";
    let html = `
        <div class="admin-content-header">
            <h2>${catName} <span style="font-weight:400;font-size:14px;color:#868E96">(${pdfs.length} file)</span></h2>
            <button class="btn btn-primary btn-sm" onclick="openUploadModal(${categoryId})">+ Upload PDF</button>
        </div>
    `;

    if (pdfs.length === 0) {
        html += `<p class="empty-state">
            <span class="empty-state-icon">📄</span>
            Chưa có tài liệu nào trong danh mục này.
        </p>`;
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
                    <a href="/pdf/${p.id}" target="_blank" class="btn btn-sm btn-secondary">Xem</a>
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
