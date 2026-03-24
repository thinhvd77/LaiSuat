# Design: 3-Level Category Hierarchy

**Date:** 2026-03-24
**Status:** Approved

## Problem

Currently the category system is locked to exactly 2 levels: 3 fixed root categories → child categories → PDFs. The user wants flexibility to create child categories for any category, enabling a 3-level tree.

## Requirements

1. **3 levels maximum**: Root (depth 0) → Level 1 (depth 1) → Level 2 (depth 2)
2. **PDFs only on leaf categories**: A category with children cannot hold PDFs
3. **3 root categories remain fixed**: "Lãi suất", "Các chương trình tín dụng ưu đãi", "Phí dịch vụ" — undeletable, uneditable
4. **No DB schema change**: The existing `parent_id` self-referencing FK already supports N-level nesting
5. **No re-parenting**: `update_category()` does not support changing `parent_id`. Out of scope.

## Design

### 1. Model (`models.py`)

Remove `is_parent` property. Add these computed properties to `Category`:

```python
@property
def depth(self):
    """0 = root, 1 = level 1, 2 = level 2 (leaf)."""
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
```

**Replace all `is_parent` usages:**
- `is_parent` (was `parent_id is None`) conflates "is root" with "has children"
- Replace with `is_leaf` / `can_have_children` / `depth == 0` as appropriate
- Existing tests that assert `is_parent` must be updated to use `depth == 0`

**`to_dict()` — recursive serialization:**
- Include `children[]` array **only when the category actually has children** (`children.count() > 0`)
- Include `pdf_count` **only when the category is a leaf** (`is_leaf == True`)
- Always include `depth`, `is_leaf`, `can_have_children` for frontend rendering decisions
- **Edge case — L1 leaf** (no children, no PDFs, but `can_have_children=True`): returns `pdf_count: 0` (it IS a leaf). The `can_have_children` flag tells the frontend it can also be a parent if children are added later.

```python
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

### 2. Routes

**`create_category()` — `POST /admin/categories`:**

Current guard: `if not parent or not parent.is_parent` (only roots can be parents).
New guard:

```python
if not parent or not parent.can_have_children:
    return {"error": "Danh mục này không thể có danh mục con"}, 400

if not parent.is_leaf and parent.pdfs.count() == 0:
    pass  # OK — parent already has children or no PDFs
elif parent.is_leaf and parent.pdfs.count() > 0:
    return {"error": "Danh mục đang có tài liệu, không thể thêm danh mục con"}, 400
```

This allows creating children under roots (depth 0) AND L1 categories (depth 1), but NOT L2 (depth 2). Also rejects adding children to a category that already has PDFs.

File upload with L2 creation is valid — L2 is always a leaf, so an optional PDF attachment works.

**`upload_pdf()` — `POST /admin/pdfs`:**

Current guard: `if cat.is_parent` (blocks roots only).
New guard — must block both roots and any non-leaf:

```python
if cat.depth == 0 or not cat.is_leaf:
    return {"error": "Chỉ upload vào danh mục lá (không có danh mục con)"}, 400
```

Root categories (depth 0) cannot hold PDFs even if they have no children, since they are fixed structural anchors.

**`update_category()` — `PUT /admin/categories/<id>`:**

No changes. Re-parenting (changing `parent_id`) is out of scope. Only `name` and `sort_order` can be updated.

**`delete_category()` — `DELETE /admin/categories/<id>`:**

Add application-level check for children. Note: the DB FK constraint (`ondelete='RESTRICT'`) already prevents this at the database level, but an explicit check provides a user-friendly Vietnamese error message.

```python
if cat.children.count() > 0:
    return {"error": "Không thể xóa danh mục còn danh mục con"}, 400
```

Keep existing check: `if cat.pdfs.count() > 0` → reject.

**`list_categories()` — `GET /api/categories`:**

No route change needed. `to_dict()` handles recursive serialization.

### 3. UI — Sidebar

**Helper function (shared pattern for both `app.js` and `admin.js`):**

Replace all shallow `p.children.find(c => c.id === id)` lookups with a recursive search:

```javascript
function findCategoryById(parents, id) {
    for (const p of parents) {
        if (p.id === id) return p;
        if (p.children) {
            for (const c of p.children) {
                if (c.id === id) return c;
                if (c.children) {
                    const found = c.children.find(gc => gc.id === id);
                    if (found) return found;
                }
            }
        }
    }
    return null;
}
```

This affects `editCategory()`, `loadPdfs()`, `loadCategories()` auto-expand, and `expandedParents` Set (which must track both L0 and L1 expanded states).

**Public sidebar (`app.js`):**

3-level nested accordion:

```
▼ Lãi suất                         ← Root: accordion toggle
   ▼ Tiết kiệm                     ← L1 with children: sub-accordion
      • Tiết kiệm online  (3)      ← L2: leaf item (click → load PDF)
      • Tiết kiệm tại quầy (5)
   • Lãi suất liên ngân hàng (2)   ← L1 leaf: click → load PDF
▼ Phí dịch vụ
   • Phí chuyển tiền (1)           ← L1 leaf
```

- Root (depth 0): `.sidebar-group` — accordion header + toggle
- L1 with children: `.sidebar-subgroup` — nested sub-accordion with its own toggle arrow
- L1 leaf (no children): `.sidebar-item` — clickable, loads PDFs
- L2: `.sidebar-item` always — clickable, loads PDFs, extra indent

**Admin sidebar (`admin.js`):**

Same structure as public, plus:
- "+" button on any category with `can_have_children` (root + L1 that has `depth < 2`)
- "✏️ 🗑️" buttons on any non-default category
- Category modal dropdown: shows root AND L1 categories, using `<optgroup>` grouped by root for clarity:

```html
<select id="cat-parent-id">
  <optgroup label="Lãi suất">
    <option value="1">Lãi suất (gốc)</option>
    <option value="4">— Tiết kiệm</option>
    <option value="5">— Cho vay</option>
  </optgroup>
  <optgroup label="Phí dịch vụ">
    <option value="3">Phí dịch vụ (gốc)</option>
  </optgroup>
</select>
```

Only categories where `can_have_children == true` appear in the dropdown.

**CSS (`style.css`):**
- `.sidebar-subgroup` styles for L1 sub-accordion (similar to `.sidebar-group` but indented)
- `.sidebar-subgroup-header` for L1 accordion header (smaller font, indent)
- Depth-based indentation via padding-left

### 4. Tests

**`test_models.py`:**
- Test `depth` property for all 3 levels (0, 1, 2)
- Test `can_have_children` (True for depth 0, 1; False for depth 2)
- Test `is_leaf` (True when no children, False when has children)
- Test `to_dict()` returns nested 3-level structure with correct keys
- Test L1 leaf `to_dict()` returns `pdf_count` (not `children`)
- Test creating 3-level chain (root → L1 → L2)
- **Update existing tests**: replace `is_parent` assertions with `depth == 0` equivalents

**`test_admin.py`:**
- Test create category as child of L1 (creates L2)
- Test reject create child of L2 (depth limit exceeded)
- Test upload PDF to L1 leaf (allowed — it's a leaf)
- Test reject upload to L1 with children (not a leaf)
- Test reject adding child to category that has PDFs
- Test delete category with children fails
- Test upload to root rejected (depth 0 never holds PDFs)

**`test_public.py`:**
- Test API returns 3-level nested structure
- Test L1 leaf appears correctly in API response (has `pdf_count`, no `children`)

### 5. Migration

No DB schema migration needed. The `parent_id` column already supports arbitrary nesting. Only code-level validation changes.

### 6. Limitations

- **No PDF reassignment**: To convert an L1 leaf (with PDFs) into an L1 parent, the admin must first delete all PDFs from it, then add children. There is no "move PDF to subcategory" feature. This is intentional for this iteration — a reassignment feature may be added later if needed.
- **No re-parenting**: Categories cannot be moved between parents. Only `name` and `sort_order` are editable.

## Files to Modify

| File | Change |
|------|--------|
| `models.py` | Remove `is_parent`. Add `depth`, `is_leaf`, `can_have_children`. Update `to_dict()` recursive. |
| `routes_admin.py` | Update validation in `create_category`, `upload_pdf`, `delete_category`. No change to `update_category`. |
| `routes_public.py` | No changes (to_dict handles recursion) |
| `static/js/app.js` | 3-level sidebar rendering, sub-accordion for L1 with children, recursive category search |
| `static/js/admin.js` | 3-level sidebar, "+" on L1, `<optgroup>` parent dropdown, recursive category search |
| `static/css/style.css` | `.sidebar-subgroup` styles, depth-based indentation |
| `tests/test_models.py` | New tests for depth, is_leaf, can_have_children. Update existing `is_parent` tests. |
| `tests/test_admin.py` | New tests for L2 creation, depth limit, leaf validation, root upload rejection |
| `tests/test_public.py` | Update to test 3-level API response |

## Risks

- **N+1 queries**: `is_leaf` uses `children.count()` and `depth` traverses parent chain (1-2 hops) in `to_dict()`. Approximately 2-3 queries per node during serialization. Acceptable at current scale (~50-100 categories). If performance becomes an issue, consider eager-loading children or adding a `has_children` denormalized column.
- **Existing data**: Current L1 categories remain L1 leaves. No data migration needed.
- **UI complexity**: Sub-accordion within accordion. Keep animations smooth with same CSS `max-height` approach.
