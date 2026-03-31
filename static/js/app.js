let currentCategoryId = null;
let currentPdfId = null;
let pdfDoc = null;
let expandedParents = new Set();

// ─── PDF.js Setup ───
const pdfjsLib = await import("/static/pdfjs/pdf.min.mjs");
pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.mjs";

// ─── Mobile Sidebar ───
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("sidebar-overlay");

function openSidebar() {
    sidebar.classList.add("open");
    overlay.classList.add("active");
}
function closeSidebar() {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
}

if (sidebarToggle) sidebarToggle.addEventListener("click", openSidebar);
if (overlay) overlay.addEventListener("click", closeSidebar);

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

function findFirstLeaf(parents) {
    for (const p of parents) {
        if (p.is_leaf) return p;
        if (p.children) {
            for (const c of p.children) {
                if (c.is_leaf) return c;
                if (c.children) {
                    for (const gc of c.children) {
                        if (gc.is_leaf) return gc;
                    }
                }
            }
        }
    }
    return null;
}

// ─── Categories (Accordion) ───
async function loadCategories() {
    const resp = await fetch("/api/categories");
    const parents = await resp.json();

    const list = document.getElementById("category-list");
    if (parents.length === 0) {
        list.innerHTML = `<p class="empty-state">
            <span class="empty-state-icon">📋</span>
            Chưa có danh mục lãi suất nào.
        </p>`;
        document.getElementById("viewer-empty").innerHTML = `
            <span class="empty-state-icon">📊</span>
            Chưa có danh mục lãi suất nào.
        `;
        return;
    }

    // Auto-expand: find which root and L1 contain the selected category
    if (expandedParents.size === 0) {
        let found = false;
        for (const p of parents) {
            if (p.id === currentCategoryId && p.is_leaf) {
                found = true;
                break;
            }
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
        if (!found) {
            // Expand first root that has any leaf descendants
            for (const p of parents) {
                if (p.children && p.children.length > 0) {
                    expandedParents.add(p.id);
                    break;
                }
            }
        }
    }

    list.innerHTML = parents
        .map((p) => {
            if (p.is_leaf) {
                return `
                <div class="sidebar-item ${p.id === currentCategoryId ? "active" : ""}" data-id="${p.id}">
                    <span class="sidebar-item-text">${p.name}</span>
                    <span class="sidebar-item-count">${p.pdf_count || 0}</span>
                </div>`;
            }

            const isExpanded = expandedParents.has(p.id);
            const totalPdfs = countPdfs(p);

            const childrenHtml = (p.children || [])
                .map((c) => {
                    if (c.is_leaf) {
                        // L1 leaf — clickable item
                        return `
                        <div class="sidebar-item ${c.id === currentCategoryId ? "active" : ""}"
                             data-id="${c.id}">
                            <span class="sidebar-item-text">${c.name}</span>
                            <span class="sidebar-item-count">${c.pdf_count}</span>
                        </div>`;
                    } else {
                        // L1 with children — sub-accordion
                        const isSubExpanded = expandedParents.has(c.id);
                        const subTotal = countPdfs(c);
                        const grandchildrenHtml = (c.children || [])
                            .map(
                                (gc) => `
                            <div class="sidebar-item ${gc.id === currentCategoryId ? "active" : ""}"
                                 data-id="${gc.id}">
                                <span class="sidebar-item-text">${gc.name}</span>
                                <span class="sidebar-item-count">${gc.pdf_count}</span>
                            </div>`
                            )
                            .join("");

                        return `
                        <div class="sidebar-subgroup ${isSubExpanded ? "expanded" : ""}">
                            <div class="sidebar-subgroup-header" data-subgroup-id="${c.id}">
                                <span class="sidebar-subgroup-name">${c.name}</span>
                                <span class="sidebar-subgroup-meta">
                                    <span class="sidebar-group-total">${subTotal}</span>
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
                        <span class="sidebar-group-total">${totalPdfs}</span>
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

    // Root accordion toggle (DOM-only)
    list.querySelectorAll(".sidebar-group-header").forEach((el) => {
        el.addEventListener("click", () => {
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

    // Sub-accordion toggle (DOM-only)
    list.querySelectorAll(".sidebar-subgroup-header").forEach((el) => {
        el.addEventListener("click", () => {
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
            closeSidebar();
        });
    });

    // Auto-select first leaf if none selected
    if (!currentCategoryId) {
        const firstLeaf = findFirstLeaf(parents);
        if (firstLeaf) {
            currentCategoryId = firstLeaf.id;
            loadCategories();
            loadPdfs(currentCategoryId);
        }
    }
}

// ─── PDFs ───
async function loadPdfs(categoryId) {
    const toolbar = document.getElementById("viewer-toolbar");
    const viewerEmpty = document.getElementById("viewer-empty");
    const select = document.getElementById("pdf-select");
    const catName = document.getElementById("category-name");

    // Use recursive search via re-fetch
    const catsResp = await fetch("/api/categories");
    const parents = await catsResp.json();
    const catObj = findCategoryById(parents, categoryId);
    if (catObj) catName.textContent = catObj.name;

    const resp = await fetch(`/api/categories/${categoryId}/pdfs`);
    const pdfs = await resp.json();

    if (pdfs.length === 0) {
        toolbar.style.display = "none";
        viewerEmpty.innerHTML = `
            <span class="empty-state-icon">📄</span>
            Chưa có tài liệu nào trong danh mục này.
        `;
        viewerEmpty.style.display = "block";
        clearPdfViewer();
        return;
    }

    toolbar.style.display = "flex";
    viewerEmpty.style.display = "none";

    select.innerHTML = pdfs
        .map((p) => `<option value="${p.id}">${p.title}</option>`)
        .join("");

    select.onchange = () => renderPdf(parseInt(select.value));

    // Auto-render first (newest)
    renderPdf(pdfs[0].id);
}

// ─── PDF Rendering ───
async function renderPdf(pdfId) {
    currentPdfId = pdfId;
    const container = document.getElementById("pdf-viewer");
    clearPdfViewer();

    try {
        pdfDoc = await pdfjsLib.getDocument(`/pdf/${pdfId}`).promise;

        for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
            const page = await pdfDoc.getPage(pageNum);
            const scale = 1.5;
            const viewport = page.getViewport({ scale });

            const canvas = document.createElement("canvas");
            canvas.className = "pdf-page";
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            container.appendChild(canvas);

            const ctx = canvas.getContext("2d");
            await page.render({ canvasContext: ctx, viewport }).promise;
        }
    } catch (err) {
        container.innerHTML = `<p class="empty-state">
            <span class="empty-state-icon">⚠️</span>
            Không tìm thấy tài liệu. Vui lòng liên hệ quản trị viên.
        </p>`;
    }
}

function clearPdfViewer() {
    const container = document.getElementById("pdf-viewer");
    container.querySelectorAll("canvas").forEach((c) => c.remove());
    if (pdfDoc) {
        pdfDoc.destroy();
        pdfDoc = null;
    }
}

// ─── Scroll-to-Top Button ───
const scrollTopBtn = document.getElementById("scroll-top-btn");
const pdfViewerEl = document.getElementById("pdf-viewer");

if (scrollTopBtn && pdfViewerEl) {
    let scrollTicking = false;
    pdfViewerEl.addEventListener("scroll", () => {
        if (!scrollTicking) {
            requestAnimationFrame(() => {
                if (pdfViewerEl.scrollTop > 300) {
                    scrollTopBtn.classList.add("visible");
                } else {
                    scrollTopBtn.classList.remove("visible");
                }
                scrollTicking = false;
            });
            scrollTicking = true;
        }
    });

    scrollTopBtn.addEventListener("click", () => {
        pdfViewerEl.scrollTo({ top: 0, behavior: "smooth" });
    });
}

// ─── Init ───
loadCategories();
