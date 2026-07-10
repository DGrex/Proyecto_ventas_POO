# TecnoStock S.A. — Sistema de Ventas, Compras y Cobros

Sistema de gestión comercial desarrollado en Django que integra control de inventario, ventas a crédito y contado, compras a proveedores, cuentas por cobrar y administración de usuarios y roles.

---

## Tabla de contenido

- [Descripción general](#descripción-general)
- [Módulos del sistema](#módulos-del-sistema)
- [Arquitectura y modelos compartidos](#arquitectura-y-modelos-compartidos)
- [Roles y permisos](#roles-y-permisos)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Requisitos previos](#requisitos-previos)
- [Instalación y ejecución](#instalación-y-ejecución)
- [Auditoría](#auditoría)
- [Exportación de reportes](#exportación-de-reportes)

---

## Descripción general

El proyecto está organizado en aplicaciones Django independientes que comparten un catálogo único de clientes, proveedores y productos, evitando duplicación de datos entre los módulos de ventas y compras.

| App | Responsabilidad |
|---|---|
| `billing` | Catálogo (marcas, grupos, productos, proveedores, clientes) y facturación de ventas |
| `purchasing` | Registro de compras a proveedores y actualización de inventario |
| `cobros` | Cuentas por cobrar: abonos sobre facturas de venta a crédito |
| `security` | Autenticación, gestión de usuarios, roles (grupos) y permisos |
| `shared` | Mixins, decoradores y utilidades reutilizadas por las demás apps (control de acceso, auditoría, exportación a PDF/Excel) |

---

## Módulos del sistema

### Ventas (`billing`)

- Gestión de catálogo: marcas, grupos de producto, proveedores, productos y clientes.
- Emisión de facturas de venta a **contado** o a **crédito** (campo `tipo_pago`).
- Cálculo automático de subtotal, impuesto y total.
- Facturas a crédito inician con `estado = PENDIENTE` y `saldo = total`; las de contado quedan `PAGADA` de inmediato.

### Compras (`purchasing`)

- Registro de compras a proveedores existentes.
- Actualización automática de stock al guardar o eliminar una compra.
- Reutiliza los modelos `Supplier` y `Product` de `billing` (ver [Arquitectura](#arquitectura-y-modelos-compartidos)).

### Cobros (`cobros`)

Módulo de cuentas por cobrar sobre facturas de venta a crédito.

- Lista únicamente las facturas con `tipo_pago='credito'` y `estado='PENDIENTE'`.
- Permite registrar uno o varios abonos (`CobroFactura`) por factura.
- Historial de pagos por factura, con opción de editar o eliminar un abono.
- **Reglas de negocio aplicadas en el modelo `CobroFactura`:**
  - No se permite abonar una factura anulada.
  - No se permite un abono negativo, igual a cero, o mayor al saldo pendiente.
  - El saldo se recalcula automáticamente en cada guardado (`saldo -= valor`).
  - Cuando el saldo llega a `0`, la factura pasa a `estado = PAGADA` automáticamente.
  - Al eliminar un abono, el saldo se repone y el estado se recalcula.
  - No se permite eliminar abonos de una factura que ya está completamente `PAGADA`.

### Seguridad (`security`)

- Registro e inicio de sesión de usuarios.
- CRUD de usuarios, roles (`Group`) y permisos (`Permission`).
- Los accesos a cada módulo están controlados por grupo (`Administrador`, `Vendedor`, `Analista de Compras`), mediante el mixin `GroupRequiredMixin`.

---

## Arquitectura y modelos compartidos

`purchasing` reutiliza directamente los modelos `Supplier` y `Product` definidos en `billing`, evitando duplicar catálogos:

```python
# purchasing/models.py
from billing.models import Supplier, Product
```

`cobros` reutiliza el modelo `Invoice` de `billing`:

```python
# cobros/models.py
from billing.models import Invoice
```

**Beneficios de este diseño:**

- Datos centralizados: `Supplier`, `Product` e `Invoice` existen una sola vez en la base de datos.
- Relaciones claras entre apps: `Purchase.supplier` → `billing.Supplier`, `PurchaseDetail.product` → `billing.Product`, `CobroFactura.factura` → `billing.Invoice`.
- El stock se actualiza desde `purchasing` sobre el mismo `Product.stock` que usa `billing`.
- Separación de precios: `billing` usa `unit_price` (venta) y `purchasing` usa `unit_cost` (compra).

---

## Roles y permisos

| Rol | Acceso |
|---|---|
| **Administrador** | Acceso total: catálogo, compras, ventas, cobros y seguridad |
| **Vendedor** | Clientes, facturación de ventas y módulo de cobros |
| **Analista de Compras** | Catálogo (marcas, grupos, proveedores, productos) y compras |

El control de acceso se implementa con los mixins de `shared/mixins.py`:

- `StaffRequiredMixin`: exige pertenecer al staff, ser superusuario, o pertenecer a `Administrador`.
- `GroupRequiredMixin`: exige pertenecer a uno de los grupos definidos en `group_required` de cada vista.

Los grupos y permisos base se pueden crear con el comando de gestión incluido:

```bash
python manage.py setup_roles
```

---

## Estructura del proyecto

```
Sales_Project_Denis/
├── billing/                  # Catálogo y facturación de ventas
│   ├── models.py              (Brand, ProductGroup, Supplier, Product, Customer, Invoice, InvoiceDetail)
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── templates/billing/
├── purchasing/                # Compras a proveedores
│   ├── models.py               (Purchase, PurchaseDetail)
│   ├── views.py
│   ├── urls.py
│   └── templates/purchasing/
├── cobros/                    # Cuentas por cobrar
│   ├── models.py                (CobroFactura)
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── templates/cobros/
├── security/                  # Autenticación, usuarios, roles y permisos
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── management/commands/setup_roles.py
│   └── templates/security/
├── shared/                    # Utilidades compartidas
│   ├── mixins.py                (StaffRequiredMixin, GroupRequiredMixin, ExportMixin)
│   ├── decorators.py             (audit_action)
│   └── validators.py
├── config/                    # Configuración del proyecto Django
│   ├── settings.py
│   └── urls.py
├── media/products/            # Imágenes de productos subidas
├── requirements.txt
└── manage.py
```

---

## Requisitos previos

- Python 3.11 o superior
- pip

---

## Instalación y ejecución

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd Sales_Project_Denis

# 2. Crear y activar un entorno virtual
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Aplicar migraciones
python manage.py migrate

# 5. Crear roles base (Administrador, Vendedor, Analista de Compras)
python manage.py setup_roles

# 6. Crear un superusuario
python manage.py createsuperuser

# 7. Levantar el servidor de desarrollo
python manage.py runserver
```

La aplicación queda disponible en `http://127.0.0.1:8000/`.

---

## Auditoría

Las acciones sobre los modelos principales (crear, editar, eliminar) quedan registradas mediante el decorador `audit_action` (`shared/decorators.py`), que imprime en consola el usuario, la acción, el método HTTP y la IP de origen. Puede redirigirse a un archivo de log configurando el logger `audit` en `settings.py`.

---

## Exportación de reportes

Los listados de `billing` incluyen exportación a **PDF** y **Excel** mediante `ExportMixin` (`shared/mixins.py`), con selección dinámica de columnas desde la interfaz.

