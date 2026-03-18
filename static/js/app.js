let currentCategoryId = null;
let currentPdfId = null;
let pdfDoc = null;

// ─── PDF.js Setup ───
const pdfjsLib = await import("/static/pdfjs/pdf.min.mjs");
pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.mjs";

// ─── Categories ───
async function loadCategories() {
    const resp = await fetch("/api/categories");
    const cats = await resp.json();

    const list = document.getElementById("category-list");
    if (cats.length === 0) {
        list.innerHTML = '<p class="empty-state">Chưa có danh mục lãi suất nào.</p>';
        document.getElementById("viewer-empty").textContent = "Chưa có danh mục lãi suất nào.";
        return;
    }

    list.innerHTML = cats
        .map(
            (c) => `
        <div class="sidebar-item ${c.id === currentCategoryId ? "active" : ""}"
             data-id="${c.id}">
            <span class="sidebar-item-text">${c.icon} ${c.name}</span>
            <span class="sidebar-item-count">${c.pdf_count}</span>
        </div>`
        )
        .join("");

    list.querySelectorAll(".sidebar-item").forEach((el) => {
        el.addEventListener("click", () => {
            currentCategoryId = parseInt(el.dataset.id);
            loadCategories();
            loadPdfs(currentCategoryId);
        });
    });

    // Auto-select first if none selected
    if (!currentCategoryId && cats.length > 0) {
        currentCategoryId = cats[0].id;
        loadCategories();
        loadPdfs(currentCategoryId);
    }
}

// ─── PDFs ───
async function loadPdfs(categoryId) {
    const toolbar = document.getElementById("viewer-toolbar");
    const viewerEmpty = document.getElementById("viewer-empty");
    const select = document.getElementById("pdf-select");
    const catName = document.getElementById("category-name");

    const catsResp = await fetch("/api/categories");
    const cats = await catsResp.json();
    const cat = cats.find((c) => c.id === categoryId);
    if (cat) catName.textContent = `${cat.icon} ${cat.name}`;

    const resp = await fetch(`/api/categories/${categoryId}/pdfs`);
    const pdfs = await resp.json();

    if (pdfs.length === 0) {
        toolbar.style.display = "none";
        viewerEmpty.textContent = "Chưa có tài liệu nào trong danh mục này.";
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
        container.innerHTML =
            '<p class="empty-state">Không tìm thấy tài liệu. Vui lòng liên hệ quản trị viên.</p>';
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

// ─── Init ───
loadCategories();
