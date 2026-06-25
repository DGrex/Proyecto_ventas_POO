# DENIS GOYES
# TecnoStock S.A. — Sistema de Ventas y Compras

## Descripción General

Este proyecto Django integra dos módulos principales:
- **`billing`**: Sistema de ventas, facturación a clientes, y gestión de catálogo (marcas, grupos, proveedores, productos, clientes).
- **`purchasing`**: Módulo de compras y reabastecimiento de inventario desde proveedores.

---

## Cómo `purchasing` reutiliza `Supplier` y `Product` de `billing`

### La idea central: un solo catálogo, dos módulos de negocio

En lugar de duplicar la información de proveedores o productos en la app `purchasing`, el módulo de compras **importa directamente** los modelos de `billing`:

```python
# purchasing/models.py
from billing.models import Supplier, Product  # Reutilizamos modelos de billing
```

Esto tiene implicaciones importantes:

| Aspecto | Detalle |
|---|---|
| **Sin duplicación de datos** | Los mismos `Supplier` y `Product` que se usan en ventas se usan en compras. No hay dos tablas de proveedores ni dos tablas de productos. |
| **Relaciones FK entre apps** | `Purchase.supplier` apunta a `billing.Supplier`, y `PurchaseDetail.product` apunta a `billing.Product`. Django gestiona FK entre apps sin problema. |
| **on_delete coherente** | `PROTECT` en `supplier` y `product` (no se puede borrar un proveedor o producto con compras asociadas); `CASCADE` en los detalles (si se borra la compra, caen sus líneas). |
| **Stock compartido** | Al guardar un `PurchaseDetail`, la señal `save()` **suma** la cantidad al `Product.stock` de `billing`. Al eliminar, la señal `post_delete` **resta** esa cantidad. El stock es siempre el mismo campo en la misma tabla. |
| **Precio vs. Costo** | `billing` usa `unit_price` (precio de venta al cliente); `purchasing` usa `unit_cost` (costo de compra al proveedor). Misma estructura de datos, distinto significado de negocio. |

### Estructura de archivos relevante

```
sales_project/
├── billing/
│   ├── models.py          ← Define Supplier, Product (y otros)
│   └── ...
└── purchasing/
    ├── models.py          ← Importa Supplier y Product de billing
    ├── forms.py           ← PurchaseForm, PurchaseDetailFormSet
    ├── views.py           ← CRUD (list, create, update, detail, delete)
    ├── urls.py            ← app_name = 'purchasing'
    └── templates/
        └── purchasing/
            ├── purchase_list.html
            ├── purchase_form.html
            ├── purchase_detail.html
            └── purchase_confirm_delete.html
```

### Flujo de una compra

1. El usuario selecciona un **Proveedor** (de `billing.Supplier`) y un número de factura del proveedor.
2. Agrega **Productos** (de `billing.Product`) con cantidades y costos unitarios.
3. Al guardar: se calculan subtotal, IVA (15%) y total; el stock de cada producto **aumenta** automáticamente.
4. Al eliminar una compra: el stock de cada producto **disminuye** nuevamente.

---

## Instalación y ejecución

```bash
# Instalar dependencias
pip install -r requirements.txt

# Aplicar migraciones
python manage.py migrate

# Crear superusuario (opcional)
python manage.py createsuperuser

# Ejecutar servidor de desarrollo
python manage.py runserver
```

Accede a `http://127.0.0.1:8000/` y navega a **Compras** en el menú principal.
