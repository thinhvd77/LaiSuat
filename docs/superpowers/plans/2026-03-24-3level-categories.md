# 3-Level Category Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the 2-level category hierarchy to 3 levels (Root → L1 → L2), allowing child categories to be created under any non-leaf category up to depth 2.

**Architecture:** Replace the `is_parent` property with `depth`, `is_leaf`, and `can_have_children` computed properties. Update route validation to use these new properties. Extend the accordion sidebar UI to render 3-level nested trees with sub-accordions for L1 categories that have children.

**Tech Stack:** Flask 3.x, SQLAlchemy, SQLite, Vanilla JS (ES modules), CSS transitions

**Spec:** `docs/superpowers/specs/2026-03-24-3level-categories-design.md`

**Test command:** `./venv/bin/pytest tests/ -v`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `models.py` | Modify (lines 35-54) | Remove `is_parent`, add `depth`/`is_leaf`/`can_have_children`, rewrite `to_dict()` |
| `routes_admin.py` | Modify (lines 106-108, 193, 237-238) | Update `create_category`, `delete_category`, `upload_pdf` validation guards |
| `static/js/app.js` | Modify (full rewrite of `loadCategories` + `loadPdfs`) | 3-level public sidebar with sub-accordion, recursive category search |
| `static/js/admin.js` | Modify (full rewrite of `loadCategories`, `editCategory`, `loadPdfs`, `_populateParentDropdown`) | 3-level admin sidebar with sub-accordion, optgroup dropdown, recursive search |
| `static/css/style.css` | Modify (after line 497) | Add `.sidebar-subgroup` styles for L1 sub-accordion |
| `tests/test_models.py` | Modify (lines 16, 29, add new tests) | Update `is_parent` assertions, add depth/is_leaf/can_have_children/3-level tests |
| `tests/test_admin.py` | Modify (add new test class) | Add L2 creation, depth limit, leaf validation, root upload rejection tests |
| `tests/test_public.py` | Modify (add new tests) | Add 3-level API response tests |

---

### Task 1: Update Category Model — Remove `is_parent`, Add New Properties

**Files:**
- Modify: `models.py:35-54`
- Test: `tests/test_models.py`

- [ ] **Step 1: Update existing tests that reference `is_parent`**

In `tests/test_models.py`, replace `is_parent` assertions with `depth`-based equivalents:

```python
# Line 16: change
assert child.is_parent is False
# to
assert child.depth == 1

# Line 29: change
assert p.is_parent is True
# to
assert p.depth == 0
```

- [ ] **Step 2: Write new model tests for `depth`, `is_leaf`, `can_have_children`**

Add to `tests/test_models.py` in class `TestCategoryModel`:

```python
def test_depth_property(self, app):
    with app.app_context():
        root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
        l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
        db.session.add(l1)
        db.session.commit()
        l2 = Category(name="Tiết kiệm online", parent_id=l1.id, sort_order=1)
        db.session.add(l2)
        db.session.commit()

        assert root.depth == 0
        assert l1.depth == 1
        assert l2.depth == 2

def test_can_have_children(self, app):
    with app.app_context():
        root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
        l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
        db.session.add(l1)
        db.session.commit()
        l2 = Category(name="Tiết kiệm online", parent_id=l1.id, sort_order=1)
        db.session.add(l2)
        db.session.commit()

        assert root.can_have_children is True
        assert l1.can_have_children is True
        assert l2.can_have_children is False

def test_is_leaf(self, app):
    with app.app_context():
        root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
        # Root with no children is technically a leaf
        assert root.is_leaf is True

        l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
        db.session.add(l1)
        db.session.commit()

        # Root now has children, no longer a leaf
        assert root.is_leaf is False
        # L1 with no children is a leaf
        assert l1.is_leaf is True

def test_to_dict_3_levels(self, app):
    with app.app_context():
        root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
        l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
        db.session.add(l1)
        db.session.commit()
        l2 = Category(name="Online", parent_id=l1.id, sort_order=1)
        db.session.add(l2)
        db.session.commit()

        d = root.to_dict()
        assert d["depth"] == 0
        assert d["is_leaf"] is False
        assert d["can_have_children"] is True
        assert "children" in d
        assert len(d["children"]) == 1

        l1_dict = d["children"][0]
        assert l1_dict["depth"] == 1
        assert l1_dict["is_leaf"] is False
        assert l1_dict["can_have_children"] is True
        assert "children" in l1_dict
        assert len(l1_dict["children"]) == 1

        l2_dict = l1_dict["children"][0]
        assert l2_dict["depth"] == 2
        assert l2_dict["is_leaf"] is True
        assert l2_dict["can_have_children"] is False
        assert "pdf_count" in l2_dict
        assert "children" not in l2_dict

def test_l1_leaf_to_dict_has_pdf_count(self, app):
    """L1 leaf (no children) should have pdf_count, not children."""
    with app.app_context():
        root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
        l1_leaf = Category(name="Liên ngân hàng", parent_id=root.id, sort_order=1)
        db.session.add(l1_leaf)
        db.session.commit()

        d = l1_leaf.to_dict()
        assert d["is_leaf"] is True
        assert d["can_have_children"] is True
        assert "pdf_count" in d
        assert "children" not in d
```

- [ ] **Step 3: Run tests — expect failures (is_parent removed, new properties missing)**

Run: `./venv/bin/pytest tests/test_models.py -v`
Expected: Multiple FAILs (properties don't exist yet)

- [ ] **Step 4: Implement model changes**

In `models.py`, replace `is_parent` property (lines 35-37) and `to_dict()` (lines 39-54) with:

```python
@property
def depth(self):
    """0 = root, 1 = level 1, 2 = level 2."""
    if self.parent_id is None:
        return 0
    if self.parent and self.parent.parent_id is None:
        return 1
    return 2

@property
def is_leaf(self):
    """True if category has no children. Only leaves can hold PDFs."""
    return self.children.count() == 0

@property
def can_have_children(self):
    """True if depth < 2 (root and level 1 can have children)."""
    return self.depth < 2

def to_dict(self):
    d = {
        "id": self.id,
        "name": self.name,
        "parent_id": self.parent_id,
        "is_default": self.is_default,
        "sort_order": self.sort_order,
        "depth": self.depth,
        "is_leaf": self.is_leaf,
        "can_have_children": self.can_have_children,
    }
    if not self.is_leaf:
        d["children"] = [
            child.to_dict()
            for child in self.children.order_by(Category.sort_order.asc())
        ]
    else:
        d["pdf_count"] = self.pdfs.count()
    return d
```

- [ ] **Step 5: Run model tests — expect all PASS**

Run: `./venv/bin/pytest tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite — expect some failures in routes tests**

Run: `./venv/bin/pytest tests/ -v`
Expected: Model tests PASS. Some admin/public tests may fail due to `is_parent` reference in `routes_admin.py` and changed `to_dict()` output shape (new fields `depth`, `is_leaf`, etc.)

- [ ] **Step 7: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "feat: replace is_parent with depth/is_leaf/can_have_children, recursive to_dict"
```

---

### Task 2: Update Route Validation — `create_category`, `upload_pdf`, `delete_category`

**Files:**
- Modify: `routes_admin.py:106-108, 190-194, 237-238`
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write new admin tests for 3-level validation**

Add a new test class `TestThreeLevelCategories` at the end of `tests/test_admin.py`:

```python
class TestThreeLevelCategories:
    def _create_l1(self, app, auth_client, name="L1 Cat"):
        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": name, "parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        return resp.get_json()["id"]

    def test_create_l2_under_l1(self, app, auth_client):
        """Can create L2 category under L1."""
        l1_id = self._create_l1(app, auth_client)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "L2 Child", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "L2 Child"
        assert data["parent_id"] == l1_id
        assert data["depth"] == 2

    def test_reject_create_child_of_l2(self, app, auth_client):
        """Cannot create child under L2 (max depth reached)."""
        l1_id = self._create_l1(app, auth_client)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "L2", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )
        l2_id = resp.get_json()["id"]

        resp = auth_client.post(
            "/admin/categories",
            data={"name": "L3 Rejected", "parent_id": str(l2_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_pdf_to_l1_leaf(self, app, auth_client):
        """Can upload PDF to L1 leaf (no children)."""
        l1_id = self._create_l1(app, auth_client)
        data = {
            "title": "PDF on L1",
            "category_id": str(l1_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "l1.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 201

    def test_reject_upload_to_l1_with_children(self, app, auth_client):
        """Cannot upload PDF to L1 that has children (not a leaf)."""
        l1_id = self._create_l1(app, auth_client)
        # Add a child to make L1 non-leaf
        auth_client.post(
            "/admin/categories",
            data={"name": "L2 Child", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )

        data = {
            "title": "Should fail",
            "category_id": str(l1_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "fail.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 400

    def test_reject_add_child_to_category_with_pdfs(self, app, auth_client):
        """Cannot add child to L1 that already has PDFs."""
        l1_id = self._create_l1(app, auth_client)
        # Upload a PDF first
        data = {
            "title": "Existing PDF",
            "category_id": str(l1_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "existing.pdf"),
        }
        auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )

        # Try to add a child
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "Should fail", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_delete_category_with_children_fails(self, app, auth_client):
        """Cannot delete L1 that has children."""
        l1_id = self._create_l1(app, auth_client)
        auth_client.post(
            "/admin/categories",
            data={"name": "L2 Child", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )

        resp = auth_client.delete(f"/admin/categories/{l1_id}")
        assert resp.status_code == 400

    def test_upload_to_root_rejected(self, app, auth_client):
        """Cannot upload PDF to root category (depth 0)."""
        parent_id = _get_parent_id(app)
        data = {
            "title": "Root upload",
            "category_id": str(parent_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "root.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: Run new tests — expect failures**

Run: `./venv/bin/pytest tests/test_admin.py::TestThreeLevelCategories -v`
Expected: Multiple FAILs (route validation not updated yet)

- [ ] **Step 3: Update `create_category()` validation**

In `routes_admin.py`, replace lines 106-108:

```python
# OLD:
parent = db.session.get(Category, int(parent_id))
if not parent or not parent.is_parent:
    return {"error": "Danh mục cha không hợp lệ"}, 400

# NEW:
parent = db.session.get(Category, int(parent_id))
if not parent or not parent.can_have_children:
    return {"error": "Danh mục này không thể có danh mục con"}, 400

if parent.pdfs.count() > 0:
    return {"error": "Danh mục đang có tài liệu, không thể thêm danh mục con"}, 400
```

- [ ] **Step 4: Update `delete_category()` — add children check**

In `routes_admin.py`, after the `is_default` check (line 191) and before the pdfs check (line 193), add:

```python
if cat.children.count() > 0:
    return {"error": "Không thể xóa danh mục còn danh mục con"}, 400
```

- [ ] **Step 5: Update `upload_pdf()` validation**

In `routes_admin.py`, replace lines 237-238:

```python
# OLD:
if cat.is_parent:
    return {"error": "Chỉ upload vào danh mục con"}, 400

# NEW:
if cat.depth == 0 or not cat.is_leaf:
    return {"error": "Chỉ upload vào danh mục lá (không có danh mục con)"}, 400
```

- [ ] **Step 6: Run all tests — expect PASS**

Run: `./venv/bin/pytest tests/ -v`
Expected: All tests PASS (48 existing + 7 new = 55)

- [ ] **Step 7: Commit**

```bash
git add routes_admin.py tests/test_admin.py
git commit -m "feat: update route validation for 3-level hierarchy"
```

---

### Task 3: Update Public API Tests

**Files:**
- Modify: `tests/test_public.py`

- [ ] **Step 1: Add 3-level API test**

Add to `TestCategoriesAPI` in `tests/test_public.py`:

```python
def test_list_categories_3_levels(self, app, client):
    """API returns 3-level nested structure."""
    with app.app_context():
        root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
        l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
        db.session.add(l1)
        db.session.commit()
        l2 = Category(name="Online", parent_id=l1.id, sort_order=1)
        db.session.add(l2)
        db.session.commit()

    resp = client.get("/api/categories")
    data = resp.get_json()
    lai_suat = data[0]
    assert lai_suat["name"] == "Lãi suất"
    assert len(lai_suat["children"]) == 1

    tiet_kiem = lai_suat["children"][0]
    assert tiet_kiem["name"] == "Tiết kiệm"
    assert "children" in tiet_kiem
    assert len(tiet_kiem["children"]) == 1
    assert tiet_kiem["children"][0]["name"] == "Online"
    assert "pdf_count" in tiet_kiem["children"][0]

def test_l1_leaf_in_api(self, app, client):
    """L1 leaf (no children) appears with pdf_count, not children."""
    with app.app_context():
        root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
        l1 = Category(name="Leaf L1", parent_id=root.id, sort_order=1)
        db.session.add(l1)
        db.session.commit()

    resp = client.get("/api/categories")
    data = resp.get_json()
    l1_data = data[0]["children"][0]
    assert l1_data["name"] == "Leaf L1"
    assert l1_data["is_leaf"] is True
    assert "pdf_count" in l1_data
    assert "children" not in l1_data
```

- [ ] **Step 2: Update existing `test_list_categories_with_children` to check new fields**

In the existing `test_list_categories_with_children`, add assertions for the new `to_dict()` fields after line 38:

```python
assert "depth" in lai_suat
assert "is_leaf" in lai_suat
```

- [ ] **Step 3: Run public tests — expect PASS**

Run: `./venv/bin/pytest tests/test_public.py -v`
Expected: All PASS

- [ ] **Step 4: Run full test suite**

Run: `./venv/bin/pytest tests/ -v`
Expected: All PASS (57 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_public.py
git commit -m "test: add 3-level category API tests"
```

---

### Task 4: CSS — Add Sub-Accordion Styles

**Files:**
- Modify: `static/css/style.css` (after line 497, before `.btn-icon-add`)

- [ ] **Step 1: Add `.sidebar-subgroup` styles**

Insert after the `.sidebar-empty` rule (line 497) and before `.btn-icon-add` (line 499):

```css
/* Sub-accordion for L1 categories with children */
.sidebar-subgroup {
    margin-bottom: 2px;
}
.sidebar-subgroup-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    cursor: pointer;
    border-radius: var(--radius-md);
    transition: all var(--transition);
    user-select: none;
}
.sidebar-subgroup-header:hover {
    background: var(--gray-100);
}
.sidebar-subgroup-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--gray-600);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.sidebar-subgroup-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}
.sidebar-subgroup-arrow {
    color: var(--gray-400);
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    flex-shrink: 0;
}
.sidebar-subgroup.expanded .sidebar-subgroup-arrow {
    transform: rotate(0deg);
}
.sidebar-subgroup:not(.expanded) .sidebar-subgroup-arrow {
    transform: rotate(-90deg);
}
.sidebar-subgroup-children {
    overflow: hidden;
    max-height: 0;
    opacity: 0;
    transition:
        max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1),
        opacity 0.25s ease;
    padding-left: 12px;
}
.sidebar-subgroup.expanded .sidebar-subgroup-children {
    max-height: 500px;
    opacity: 1;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/css/style.css
git commit -m "style: add sub-accordion CSS for 3-level sidebar"
```

---

### Task 5: Public Sidebar JS — 3-Level Rendering

**Files:**
- Modify: `static/js/app.js` (rewrite `loadCategories` and `loadPdfs`)

- [ ] **Step 1: Add `findCategoryById` helper**

Add after the `closeSidebar()` function (after line 22), before `loadCategories`:

```javascript
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
```

- [ ] **Step 2: Add `countPdfs` helper for total count across nested children**

```javascript
function countPdfs(cat) {
    if (cat.is_leaf) return cat.pdf_count || 0;
    if (!cat.children) return 0;
    return cat.children.reduce((sum, c) => sum + countPdfs(c), 0);
}
```

- [ ] **Step 3: Rewrite `loadCategories` for 3-level rendering**

Replace the entire `loadCategories` function. Key changes:
- L1 children rendering: if `c.is_leaf` → render as `.sidebar-item` (clickable). If `c.children` → render as `.sidebar-subgroup` (sub-accordion with its own toggle).
- `expandedParents` tracks IDs of both root and L1 categories that are expanded.
- Auto-expand logic must search 3 levels deep for the selected category.

```javascript
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

function findFirstLeaf(parents) {
    for (const p of parents) {
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
```

- [ ] **Step 4: Update `loadPdfs` to use `findCategoryById` instead of shallow search**

Replace the category name lookup in `loadPdfs` (lines 139-150):

```javascript
async function loadPdfs(categoryId) {
    const toolbar = document.getElementById("viewer-toolbar");
    const viewerEmpty = document.getElementById("viewer-empty");
    const select = document.getElementById("pdf-select");
    const catName = document.getElementById("category-name");

    // Use cached data from last loadCategories via re-fetch
    const catsResp = await fetch("/api/categories");
    const parents = await catsResp.json();
    const catObj = findCategoryById(parents, categoryId);
    if (catObj) catName.textContent = catObj.name;

    // ... rest of function stays the same from line 152 onward
```

- [ ] **Step 5: Manual browser test**

Open `http://localhost:5000` and verify:
- Root categories show as top-level accordion
- L1 with children renders as sub-accordion inside root
- L1 leaf renders as clickable item
- L2 renders as clickable item inside sub-accordion
- Clicking items loads PDFs
- Expand/collapse is smooth and DOM-only

- [ ] **Step 6: Commit**

```bash
git add static/js/app.js
git commit -m "feat: public sidebar 3-level accordion rendering"
```

---

### Task 6: Admin Sidebar JS — 3-Level Rendering + Modal Dropdown

**Files:**
- Modify: `static/js/admin.js` (rewrite `loadCategories`, `_populateParentDropdown`, `editCategory`, `loadPdfs`)

- [ ] **Step 1: Add `findCategoryById` and `countPdfs` helpers**

Add after `closeAdminSidebar()` (line 36):

```javascript
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
```

- [ ] **Step 2: Rewrite `loadCategories` for 3-level admin sidebar**

Replace the entire `loadCategories` function (lines 44-132) with full 3-level rendering including admin action buttons:

```javascript
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
                        // L1 leaf — clickable item with edit/delete
                        return `
                        <div class="sidebar-item ${c.id === currentCategoryId ? "active" : ""}"
                             data-id="${c.id}">
                            <span class="sidebar-item-text">${c.name}</span>
                            <span class="sidebar-item-count">${c.pdf_count}</span>
                            <div class="sidebar-item-actions">
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
```

Note: Key differences from public sidebar:
- Root header: "+" button with `onclick="openAddCategoryForParent(${p.id}, event)"` + `e.target.closest(".btn-icon-add")` guard on toggle
- L1 subgroup header: "✏️ 🗑️" buttons + conditional "+" button (if `can_have_children`) + guards for both `.btn-icon` and `.btn-icon-add` on toggle
- L1 leaf items: "✏️ 🗑️" action buttons (hover-reveal via CSS)
- L2 items: "✏️ 🗑️" action buttons
- No auto-select first leaf (admin starts with "Chọn danh mục để quản lý" empty state)

- [ ] **Step 3: Rewrite `_populateParentDropdown` with `<optgroup>`**

```javascript
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
```

- [ ] **Step 4: Update `editCategory` to use recursive search**

Replace the shallow search (lines 164-171):

```javascript
async function editCategory(id, event) {
    event.stopPropagation();
    const cat = findCategoryById(categoriesData, id);
    if (!cat) return;

    document.getElementById("category-modal-title").textContent = "Sửa danh mục";
    document.getElementById("cat-name").value = cat.name;
    document.getElementById("cat-id").value = id;
    document.getElementById("cat-file-section").style.display = "none";
    document.getElementById("cat-parent-id").closest(".form-group").style.display = "none";
    showModal("category-modal");
}
```

- [ ] **Step 5: Update `loadPdfs` to use recursive search**

Replace the shallow category search (lines 284-291):

```javascript
async function loadPdfs(categoryId) {
    const catObj = findCategoryById(categoriesData, categoryId);
    // ... rest stays the same, using catObj
```

- [ ] **Step 6: Update `openAddCategoryForParent` — works for both root and L1**

The existing function already accepts any `parentId` and pre-fills the dropdown, so it works for L1 "+" buttons too. No code change needed — just call it from the new L1 subgroup header "+" button (already wired in Step 2).

- [ ] **Step 7: Manual browser test**

Open `http://localhost:5000/admin` and verify:
- 3-level accordion renders correctly
- "+" on root header adds child to root (L1)
- "+" on L1 subgroup header adds child to L1 (L2)
- Edit/delete buttons work on L1 and L2
- Parent dropdown shows optgroups with root + L1 options
- Creating L2 category works

- [ ] **Step 8: Commit**

```bash
git add static/js/admin.js
git commit -m "feat: admin sidebar 3-level accordion with optgroup dropdown"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `./venv/bin/pytest tests/ -v`
Expected: All PASS (57 tests)

- [ ] **Step 2: Manual smoke test — public**

1. Open `http://localhost:5000`
2. Verify 3-level accordion renders
3. Click L2 items — PDFs load
4. Click L1 leaf items — PDFs load
5. Expand/collapse L1 sub-accordion — smooth, DOM-only

- [ ] **Step 3: Manual smoke test — admin**

1. Open `http://localhost:5000/admin`
2. Create L1 category under "Lãi suất" via "+" button
3. Create L2 category under the new L1 via "+" button
4. Upload PDF to L2
5. Try to create L3 under L2 — should fail
6. Try to upload PDF to L1 with children — should fail
7. Edit L2 name — should work
8. Delete L2 — should work
9. Delete L1 — should work (now empty)

- [ ] **Step 4: Commit any fixes**

If any issues found, fix and commit.

- [ ] **Step 5: Final commit — update CLAUDE.md**

Update CLAUDE.md to reflect the 3-level hierarchy change (replace "two blueprints" category description, add depth info).

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for 3-level category hierarchy"
```
