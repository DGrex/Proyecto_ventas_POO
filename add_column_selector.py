import os
import re

DROPDOWN_HTML = """
        <!-- Columnas a Mostrar / Exportar -->
        <div class="col-md-3">
          <div class="filter-label"><i class="fas fa-columns me-1"></i>Columnas (Mostrar/Exportar)</div>
          <div class="dropdown">
            <button class="form-select form-select-sm text-start d-flex justify-content-between align-items-center" type="button" id="columnSelectDropdown" data-bs-toggle="dropdown" aria-expanded="false" data-bs-auto-close="outside" style="background-image: none; padding-right: 10px;">
              <span id="columnSelectLabel" class="text-truncate" style="max-width: 150px; display: inline-block;">
                Cargando...
              </span>
              <i class="fas fa-chevron-down text-muted" style="font-size: 0.7rem;"></i>
            </button>
            <div class="dropdown-menu p-3 shadow border-0" aria-labelledby="columnSelectDropdown" style="min-width: 250px; border-radius: 10px; max-height: 300px; overflow-y: auto; z-index: 1050;">
              <div class="d-flex justify-content-between align-items-center mb-2 pb-2 border-bottom">
                <span class="fw-bold text-dark" style="font-size: 0.8rem;">Columnas</span>
                <div>
                  <button type="button" class="btn btn-link btn-xs p-0 text-decoration-none me-2" id="selectAllColumns" style="font-size: 0.75rem; color: #b05027;">Todas</button>
                  <button type="button" class="btn btn-link btn-xs p-0 text-decoration-none text-danger" id="clearAllColumns" style="font-size: 0.75rem;">Ninguna</button>
                </div>
              </div>
              {% for col_id, col_name in available_columns %}
                <div class="form-check mb-2">
                  <input class="form-check-input col-checkbox" type="checkbox" name="columns" id="col_{{ col_id }}" value="{{ col_id }}" {% if col_id in selected_columns %}checked{% endif %} style="cursor: pointer;">
                  <label class="form-check-label text-dark" style="font-size: 0.85rem; cursor: pointer; user-select: none;" for="col_{{ col_id }}">
                    {{ col_name }}
                  </label>
                </div>
              {% endfor %}
            </div>
          </div>
        </div>
"""

JS_HTML = """
<!-- Column selector dynamic label script -->
<script>
  document.addEventListener("DOMContentLoaded", function() {
    const checkboxes = document.querySelectorAll('.col-checkbox');
    const label = document.getElementById('columnSelectLabel');
    const selectAllBtn = document.getElementById('selectAllColumns');
    const clearAllBtn = document.getElementById('clearAllColumns');

    function updateLabel() {
      if (!label) return;
      const checkedBoxes = document.querySelectorAll('.col-checkbox:checked');
      const checkedCount = checkedBoxes.length;
      const totalCount = checkboxes.length;
      
      if (checkedCount === totalCount) {
        label.textContent = "Todas";
      } else if (checkedCount === 0) {
        label.textContent = "Ninguna";
      } else {
        const checkedNames = [];
        checkedBoxes.forEach(cb => {
          checkedNames.push(cb.nextElementSibling.textContent.trim());
        });
        label.textContent = checkedNames.join(', ');
      }
    }

    checkboxes.forEach(cb => {
      cb.addEventListener('change', updateLabel);
    });

    if (selectAllBtn) {
      selectAllBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        checkboxes.forEach(cb => cb.checked = true);
        updateLabel();
      });
    }

    if (clearAllBtn) {
      clearAllBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        checkboxes.forEach(cb => cb.checked = false);
        updateLabel();
      });
    }

    updateLabel();
  });
</script>
"""

FILES = [
    './billing/templates/billing/brand_list.html',
    './billing/templates/billing/customer_list.html',
    './billing/templates/billing/invoice_list.html',
    './billing/templates/billing/productgroup_list.html',
    './billing/templates/billing/supplier_list.html',
    './purchasing/templates/purchasing/purchase_list.html'
]

for path in FILES:
    if not os.path.exists(path):
        continue
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already added
    if 'columnSelectDropdown' in content:
        print(f"Skipping {path}, already has columns filter.")
        continue
        
    # We want to add the dropdown right before the submit buttons
    # submit buttons usually start with:
    # <div class="col-md-something d-flex gap-2 justify-content-end">
    
    # Let's find the action row:
    action_row = re.search(r'(<div class="col-md-\d+(?: d-flex gap-2 justify-content-end)?">[\s\n]*<button type="submit")', content)
    if action_row:
        content = content.replace(action_row.group(1), DROPDOWN_HTML + "\n        " + action_row.group(1))
    
    # Add JS at the end
    if '<!-- Column selector dynamic label script -->' not in content:
        content = content.replace('{% endblock %}', JS_HTML + '\n{% endblock %}')
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
