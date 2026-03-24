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

## Design

### 1. Model (`models.py`)

Add computed properties to `Category`:

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

**`is_parent` property**: Remove or replace. Currently `parent_id is None`. This conflates "is root" with "has children". Replace all usages with `is_leaf` / `can_have_children` / `depth == 0` as appropriate.

**`to_dict()`**: Recursive for all levels. Each node includes `children[]` if it has children, `pdf_count` if it's a leaf. Also includes `depth`, `is_leaf`, `can_have_children` for the frontend.

### 2. Routes

**`create_category()` — `POST /admin/categories`:**
- Validate `parent.can_have_children` (replaces `parent.is_parent`)
- Validate parent is not a leaf with existing PDFs (adding a child would orphan PDFs)
- File upload logic unchanged

**`upload_pdf()` — `POST /admin/pdfs`:**
- Validate `cat.is_leaf` (replaces `not cat.is_parent`)

**`delete_category()` — `DELETE /admin/categories/<id>`:**
- Add check: if category has children → reject (must delete children first)
- Keep check: if category has PDFs → reject

**`list_categories()` — `GET /api/categories`:**
- No route change needed. `to_dict()` handles recursive serialization.

### 3. UI — Sidebar

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
- L1 with children: `.sidebar-subgroup` — nested sub-accordion with its own toggle
- L1 leaf (no children): `.sidebar-item` — clickable, loads PDFs
- L2: `.sidebar-item` always — clickable, loads PDFs, extra indent

**Admin sidebar (`admin.js`):**
Same structure as public, plus:
- "+" button on any category with `can_have_children` (root + L1)
- "✏️ 🗑️" buttons on any non-default category
- Category modal dropdown shows root AND L1 categories (grouped by root)

**CSS (`style.css`):**
- `.sidebar-subgroup` styles for L1 sub-accordion
- Depth-based indentation (padding-left increases per level)

### 4. Tests

**`test_models.py`:**
- Test `depth` property for all 3 levels
- Test `can_have_children` (True for depth 0, 1; False for depth 2)
- Test `is_leaf` (True when no children, False when has children)
- Test `to_dict()` returns nested 3-level structure
- Test creating 3-level chain

**`test_admin.py`:**
- Test create category as child of L1 (creates L2)
- Test reject create child of L2 (depth limit)
- Test upload PDF to L1 leaf (allowed)
- Test reject upload to L1 with children (not a leaf)
- Test reject adding child to category that has PDFs
- Test delete category with children fails

**`test_public.py`:**
- Test API returns 3-level nested structure
- Test L1 leaf appears correctly in API response

### 5. Migration

No DB schema migration needed. The `parent_id` column already supports arbitrary nesting. Only code-level validation changes.

## Files to Modify

| File | Change |
|------|--------|
| `models.py` | Replace `is_parent` with `depth`, `is_leaf`, `can_have_children`. Update `to_dict()` |
| `routes_admin.py` | Update validation in `create_category`, `upload_pdf`, `delete_category` |
| `routes_public.py` | No changes (to_dict handles recursion) |
| `static/js/app.js` | 3-level sidebar rendering, sub-accordion for L1 with children |
| `static/js/admin.js` | 3-level sidebar, "+" on L1, grouped parent dropdown in modal |
| `static/css/style.css` | `.sidebar-subgroup` styles, depth-based indentation |
| `tests/test_models.py` | New tests for depth, is_leaf, can_have_children, 3-level to_dict |
| `tests/test_admin.py` | New tests for L2 creation, depth limit, leaf validation |
| `tests/test_public.py` | Update to test 3-level API response |

## Risks

- **Performance**: `depth` property traverses parent chain (max 2 hops). Acceptable for 3 levels.
- **Existing data**: Current L1 categories remain L1 leaves. No data migration needed.
- **UI complexity**: Sub-accordion within accordion. Keep animations smooth with same CSS `max-height` approach.
