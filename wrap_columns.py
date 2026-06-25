import os

replacements = {
    './billing/templates/billing/brand_list.html': [
        ('<th>Nombre</th>', "{% if 'name' in selected_columns %}<th>Nombre</th>{% endif %}"),
        ('<th>Descripción</th>', "{% if 'description' in selected_columns %}<th>Descripción</th>{% endif %}"),
        ('<th class="text-center">Activa</th>', "{% if 'is_active' in selected_columns %}<th class=\"text-center\">Activa</th>{% endif %}"),
        ('<th>Creada</th>', "{% if 'created_at' in selected_columns %}<th>Creada</th>{% endif %}"),
        ('<td class="fw-semibold">{{ brand.name }}</td>', "{% if 'name' in selected_columns %}<td class=\"fw-semibold\">{{ brand.name }}</td>{% endif %}"),
        ('<td class="text-muted small">{{ brand.description|default:"—"|truncatechars:100 }}</td>', "{% if 'description' in selected_columns %}<td class=\"text-muted small\">{{ brand.description|default:\"—\"|truncatechars:100 }}</td>{% endif %}"),
        ('<td class="text-center">\n          {% if brand.is_active %}', "{% if 'is_active' in selected_columns %}<td class=\"text-center\">\n          {% if brand.is_active %}"),
        ('{% endif %}\n        </td>\n        <td>{{ brand.created_at|date:"d/m/Y" }}</td>', "{% endif %}\n        </td>{% endif %}\n        {% if 'created_at' in selected_columns %}<td>{{ brand.created_at|date:\"d/m/Y\" }}</td>{% endif %}"),
        ('<td colspan="5"', '<td colspan="100"')
    ],
    './billing/templates/billing/customer_list.html': [
        ('<th>DNI/RUC</th>', "{% if 'dni' in selected_columns %}<th>DNI/RUC</th>{% endif %}"),
        ('<th>Nombres</th>', "{% if 'first_name' in selected_columns %}<th>Nombres</th>{% endif %}"),
        ('<th>Apellidos</th>', "{% if 'last_name' in selected_columns %}<th>Apellidos</th>{% endif %}"),
        ('<th>Email</th>', "{% if 'email' in selected_columns %}<th>Email</th>{% endif %}"),
        ('<th>Teléfono</th>', "{% if 'phone' in selected_columns %}<th>Teléfono</th>{% endif %}"),
        ('<th>Dirección</th>', "{% if 'address' in selected_columns %}<th>Dirección</th>{% endif %}"),
        ('<th class="text-center">Estado</th>', "{% if 'is_active' in selected_columns %}<th class=\"text-center\">Estado</th>{% endif %}"),
        ('<td class="fw-semibold font-monospace">{{ item.dni }}</td>', "{% if 'dni' in selected_columns %}<td class=\"fw-semibold font-monospace\">{{ item.dni }}</td>{% endif %}"),
        ('<td>{{ item.first_name }}</td>', "{% if 'first_name' in selected_columns %}<td>{{ item.first_name }}</td>{% endif %}"),
        ('<td>{{ item.last_name }}</td>', "{% if 'last_name' in selected_columns %}<td>{{ item.last_name }}</td>{% endif %}"),
        ('<td class="text-muted small">{{ item.email|default:"—" }}</td>', "{% if 'email' in selected_columns %}<td class=\"text-muted small\">{{ item.email|default:\"—\" }}</td>{% endif %}"),
        ('<td>{{ item.phone|default:"—" }}</td>', "{% if 'phone' in selected_columns %}<td>{{ item.phone|default:\"—\" }}</td>{% endif %}"),
        ('<td class="text-muted small">{{ item.address|default:"—"|truncatechars:40 }}</td>', "{% if 'address' in selected_columns %}<td class=\"text-muted small\">{{ item.address|default:\"—\"|truncatechars:40 }}</td>{% endif %}"),
        ('<td class="text-center">\n          {% if item.is_active %}', "{% if 'is_active' in selected_columns %}<td class=\"text-center\">\n          {% if item.is_active %}"),
        ('{% endif %}\n        </td>\n        <td class="text-center text-nowrap">', "{% endif %}\n        </td>{% endif %}\n        <td class=\"text-center text-nowrap\">"),
        ('<td colspan="8"', '<td colspan="100"')
    ],
    './billing/templates/billing/invoice_list.html': [
        ('<th>#</th>', "{% if 'id' in selected_columns %}<th>#</th>{% endif %}"),
        ('<th>Cliente</th>', "{% if 'customer.full_name' in selected_columns %}<th>Cliente</th>{% endif %}"),
        ('<th>Fecha</th>', "{% if 'invoice_date' in selected_columns %}<th>Fecha</th>{% endif %}"),
        ('<th class="text-end">Subtotal</th>', "{% if 'subtotal' in selected_columns %}<th class=\"text-end\">Subtotal</th>{% endif %}"),
        ('<th class="text-end">Impuesto</th>', "{% if 'tax' in selected_columns %}<th class=\"text-end\">Impuesto</th>{% endif %}"),
        ('<th class="text-end">Total</th>', "{% if 'total' in selected_columns %}<th class=\"text-end\">Total</th>{% endif %}"),
        ('<td class="text-muted small">{{ inv.id }}</td>', "{% if 'id' in selected_columns %}<td class=\"text-muted small\">{{ inv.id }}</td>{% endif %}"),
        ('<td class="fw-semibold">{{ inv.customer }}</td>', "{% if 'customer.full_name' in selected_columns %}<td class=\"fw-semibold\">{{ inv.customer }}</td>{% endif %}"),
        ('<td>{{ inv.invoice_date|date:"d/m/Y" }}</td>', "{% if 'invoice_date' in selected_columns %}<td>{{ inv.invoice_date|date:\"d/m/Y\" }}</td>{% endif %}"),
        ('<td class="text-end">${{ inv.subtotal }}</td>', "{% if 'subtotal' in selected_columns %}<td class=\"text-end\">${{ inv.subtotal }}</td>{% endif %}"),
        ('<td class="text-end">${{ inv.tax }}</td>', "{% if 'tax' in selected_columns %}<td class=\"text-end\">${{ inv.tax }}</td>{% endif %}"),
        ('<td class="text-end fw-bold">${{ inv.total }}</td>', "{% if 'total' in selected_columns %}<td class=\"text-end fw-bold\">${{ inv.total }}</td>{% endif %}"),
        ('<td colspan="7"', '<td colspan="100"')
    ],
    './billing/templates/billing/productgroup_list.html': [
        ('<th>ID</th>', "{% if 'id' in selected_columns %}<th>ID</th>{% endif %}"),
        ('<th>Nombre</th>', "{% if 'name' in selected_columns %}<th>Nombre</th>{% endif %}"),
        ('<th class="text-center">Estado</th>', "{% if 'is_active' in selected_columns %}<th class=\"text-center\">Estado</th>{% endif %}"),
        ('<td class="text-muted small">{{ item.id }}</td>', "{% if 'id' in selected_columns %}<td class=\"text-muted small\">{{ item.id }}</td>{% endif %}"),
        ('<td class="fw-semibold">{{ item.name }}</td>', "{% if 'name' in selected_columns %}<td class=\"fw-semibold\">{{ item.name }}</td>{% endif %}"),
        ('<td class="text-center">\n          {% if item.is_active %}', "{% if 'is_active' in selected_columns %}<td class=\"text-center\">\n          {% if item.is_active %}"),
        ('{% endif %}\n        </td>\n        <td class="text-center">', "{% endif %}\n        </td>{% endif %}\n        <td class=\"text-center\">"),
        ('<td colspan="4"', '<td colspan="100"')
    ],
    './billing/templates/billing/supplier_list.html': [
        ('<th>Empresa</th>', "{% if 'name' in selected_columns %}<th>Empresa</th>{% endif %}"),
        ('<th>Contacto</th>', "{% if 'contact_name' in selected_columns %}<th>Contacto</th>{% endif %}"),
        ('<th>Email</th>', "{% if 'email' in selected_columns %}<th>Email</th>{% endif %}"),
        ('<th>Teléfono</th>', "{% if 'phone' in selected_columns %}<th>Teléfono</th>{% endif %}"),
        ('<th class="text-center">Estado</th>', "{% if 'is_active' in selected_columns %}<th class=\"text-center\">Estado</th>{% endif %}"),
        ('<td class="fw-semibold">{{ item.name }}</td>', "{% if 'name' in selected_columns %}<td class=\"fw-semibold\">{{ item.name }}</td>{% endif %}"),
        ('<td>{{ item.contact_name|default:"—" }}</td>', "{% if 'contact_name' in selected_columns %}<td>{{ item.contact_name|default:\"—\" }}</td>{% endif %}"),
        ('<td class="text-muted small">{{ item.email|default:"—" }}</td>', "{% if 'email' in selected_columns %}<td class=\"text-muted small\">{{ item.email|default:\"—\" }}</td>{% endif %}"),
        ('<td>{{ item.phone|default:"—" }}</td>', "{% if 'phone' in selected_columns %}<td>{{ item.phone|default:\"—\" }}</td>{% endif %}"),
        ('<td class="text-center">\n          {% if item.is_active %}', "{% if 'is_active' in selected_columns %}<td class=\"text-center\">\n          {% if item.is_active %}"),
        ('{% endif %}\n        </td>\n        <td class="text-center">', "{% endif %}\n        </td>{% endif %}\n        <td class=\"text-center\">"),
        ('<td colspan="6"', '<td colspan="100"')
    ],
    './purchasing/templates/purchasing/purchase_list.html': [
        ('<th>#</th>', "{% if 'id' in selected_columns %}<th>#</th>{% endif %}"),
        ('<th>Proveedor</th>', "{% if 'supplier' in selected_columns %}<th>Proveedor</th>{% endif %}"),
        ('<th>Nº Factura Proveedor</th>', "{% if 'document_number' in selected_columns %}<th>Nº Factura Proveedor</th>{% endif %}"),
        ('<th>Fecha Compra</th>', "{% if 'purchase_date' in selected_columns %}<th>Fecha Compra</th>{% endif %}"),
        ('<th class="text-end">Subtotal</th>', "{% if 'subtotal' in selected_columns %}<th class=\"text-end\">Subtotal</th>{% endif %}"),
        ('<th class="text-end">Impuesto</th>', "{% if 'tax' in selected_columns %}<th class=\"text-end\">Impuesto</th>{% endif %}"),
        ('<th class="text-end">Total</th>', "{% if 'total' in selected_columns %}<th class=\"text-end\">Total</th>{% endif %}"),
        ('<td class="text-muted small">{{ item.id }}</td>', "{% if 'id' in selected_columns %}<td class=\"text-muted small\">{{ item.id }}</td>{% endif %}"),
        ('<td class="fw-semibold">{{ item.supplier.name }}</td>', "{% if 'supplier' in selected_columns %}<td class=\"fw-semibold\">{{ item.supplier.name }}</td>{% endif %}"),
        ('<td><code>{{ item.document_number }}</code></td>', "{% if 'document_number' in selected_columns %}<td><code>{{ item.document_number }}</code></td>{% endif %}"),
        ('<td>{{ item.purchase_date|date:"d/m/Y H:i" }}</td>', "{% if 'purchase_date' in selected_columns %}<td>{{ item.purchase_date|date:\"d/m/Y H:i\" }}</td>{% endif %}"),
        ('<td class="text-end">${{ item.subtotal }}</td>', "{% if 'subtotal' in selected_columns %}<td class=\"text-end\">${{ item.subtotal }}</td>{% endif %}"),
        ('<td class="text-end">${{ item.tax }}</td>', "{% if 'tax' in selected_columns %}<td class=\"text-end\">${{ item.tax }}</td>{% endif %}"),
        ('<td class="text-end fw-bold">${{ item.total }}</td>', "{% if 'total' in selected_columns %}<td class=\"text-end fw-bold\">${{ item.total }}</td>{% endif %}"),
        ('<td colspan="8"', '<td colspan="100"')
    ]
}

for filepath, pairs in replacements.items():
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r') as f:
        content = f.read()
    
    for old, new in pairs:
        if new not in content:
            content = content.replace(old, new)
            
    with open(filepath, 'w') as f:
        f.write(content)
