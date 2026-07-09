# TecnoStock S.A. — Sistema de Ventas y Compras

## Descripción general

Este proyecto Django integra dos aplicaciones principales:

- **`billing`**: gestión de ventas, facturación a clientes y catálogo de marcas, grupos, proveedores, productos y clientes.
- **`purchasing`**: módulo de compras para reabastecer inventario desde proveedores.

El diseño busca mantener un catálogo único y coherente entre ventas y compras, usando los mismos modelos de proveedores y productos en ambas aplicaciones.

---

## Arquitectura principal

### Reutilización de modelos entre apps

La app `purchasing` reutiliza directamente los modelos `Supplier` y `Product` definidos en `billing`:

```python
# purchasing/models.py
from billing.models import Supplier, Product
```

Esto evita duplicar los datos y permite que las operaciones de ventas y compras compartan el mismo stock y los mismos proveedores.

### Beneficios clave

- **Datos centralizados**: `Supplier` y `Product` existen una sola vez en la base de datos.
- **Relaciones entre apps**: `Purchase.supplier` referencia a `billing.Supplier` y `PurchaseDetail.product` referencia a `billing.Product`.
- **Gestión de stock única**: el stock se actualiza desde el módulo de compras usando el campo `Product.stock` en `billing`.
- **Distinción clara de precios**: `billing` usa `unit_price` para ventas; `purchasing` usa `unit_cost` para compras.

---

## Funcionamiento del módulo de compras

### Flujo de una compra

1. Se selecciona un **Proveedor** existente.
2. Se agrega uno o varios **Productos** con cantidad y precio de compra.
3. Al guardar la compra, se calculan subtotal, IVA y total.
4. El stock del producto se incrementa automáticamente.
5. Si se elimina una compra, el stock asociado se ajusta hacia abajo.

### Relaciones y comportamiento

- `Purchase.supplier`: `ForeignKey` a `billing.Supplier` con `PROTECT`.
- `PurchaseDetail.product`: `ForeignKey` a `billing.Product` con `PROTECT`.
- `PurchaseDetail` usa `unit_cost` para registrar el costo de compra.
- Los productos y proveedores se crean y administran desde `billing`, mientras que las compras se administran desde `purchasing`.

---

## Estructura relevante

```
sales_project/
├── billing/
│   ├── admin.py
│   ├── forms.py
│   ├── models.py
│   ├── templates/billing/
│   └── urls.py
└── purchasing/
    ├── admin.py
    ├── forms.py
    ├── models.py
    ├── templates/purchasing/
    └── urls.py
```

---

## Instalación y ejecución

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Luego abre `http://127.0.0.1:8000/` y navega por las secciones de ventas y compras.

---

## Notas adicionales

- Usa el panel de administración para crear marcas, grupos, proveedores, productos y clientes.
- Desde la interfaz de compras puedes ingresar facturas de proveedor y actualizar inventario.
- El módulo de ventas utiliza el mismo catálogo de `billing`, evitando inconsistencias entre apps.
