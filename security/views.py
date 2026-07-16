import random
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import login as auth_login
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.shortcuts import redirect, render, get_object_or_404

from django.db.models import Count, Q
from shared.mixins import GroupRequiredMixin, PermissionOrRedirectMixin, ExportMixin
from shared.notifications import send_user_activation_email, send_2fa_code_email
from .forms import AdminUserCreateForm, UserUpdateForm, GroupForm, PermissionForm

# === MIXIN BASE: SOLO ADMINISTRADOR ===
class AdminOnlyMixin(LoginRequiredMixin, GroupRequiredMixin):
    """Combina login + rol Administrador (el superusuario siempre pasa)."""
    group_required = ['Administrador']
    group_redirect_url = '/'

# === AUTENTICACIÓN (CBV) ===
# NOTA: el auto-registro público fue eliminado a propósito. Los usuarios
# solo pueden ser creados por un Administrador (ver UserCreateView abajo).

class SecurityLoginView(LoginView):
    """
    Login con CBV. Ya no inicia sesión directamente: valida usuario/contraseña
    y, si son correctos, dispara la verificación de 2 pasos por correo.
    """
    template_name = 'registration/login.html'

    def form_valid(self, form):
        user = form.get_user()

        if not user.email:
            messages.error(
                self.request,
                'Tu cuenta no tiene un correo registrado, por lo que no se puede '
                'enviar el código de verificación. Contacta a un administrador.'
            )
            return self.form_invalid(form)

        codigo = f'{random.randint(0, 999999):06d}'
        self.request.session['2fa_user_id'] = user.id
        self.request.session['2fa_codigo'] = codigo
        self.request.session['2fa_expira'] = (timezone.now() + timedelta(minutes=10)).isoformat()
        self.request.session['2fa_intentos'] = 0

        ok, msg = send_2fa_code_email(user, codigo)
        if not ok:
            messages.error(self.request, f'No se pudo enviar el código de verificación: {msg}')
            return self.form_invalid(form)

        messages.info(self.request, f'Enviamos un código de verificación a {user.email}.')
        return redirect('security:verify_2fa')


class Verify2FAView(View):
    """Segunda etapa del login: valida el código de 6 dígitos enviado por correo."""
    template_name = 'registration/verify_2fa.html'
    max_intentos = 5
    expiracion_minutos = 10

    def get(self, request):
        if not request.session.get('2fa_user_id'):
            messages.error(request, 'Primero debes iniciar sesión con tu usuario y contraseña.')
            return redirect('security:login')
        user = get_object_or_404(User, pk=request.session['2fa_user_id'])
        return render(request, self.template_name, {'user_email': user.email})

    def post(self, request):
        user_id = request.session.get('2fa_user_id')
        codigo_guardado = request.session.get('2fa_codigo')
        expira_str = request.session.get('2fa_expira')
        intentos = request.session.get('2fa_intentos', 0)

        if not user_id or not codigo_guardado or not expira_str:
            messages.error(request, 'Tu sesión de verificación expiró. Inicia sesión de nuevo.')
            return redirect('security:login')

        if timezone.now() > parse_datetime(expira_str):
            self._limpiar_sesion_2fa(request)
            messages.error(request, 'El código expiró. Inicia sesión de nuevo para recibir uno nuevo.')
            return redirect('security:login')

        if intentos >= self.max_intentos:
            self._limpiar_sesion_2fa(request)
            messages.error(request, 'Demasiados intentos fallidos. Inicia sesión de nuevo.')
            return redirect('security:login')

        codigo_ingresado = request.POST.get('codigo', '').strip()

        if codigo_ingresado == codigo_guardado:
            user = get_object_or_404(User, pk=user_id)
            auth_login(request, user)
            self._limpiar_sesion_2fa(request)
            messages.success(request, f'¡Bienvenido, {user.username}!')
            return redirect('billing:home')

        request.session['2fa_intentos'] = intentos + 1
        restantes = self.max_intentos - (intentos + 1)
        messages.error(request, f'Código incorrecto. Te quedan {restantes} intento(s).')
        user = get_object_or_404(User, pk=user_id)
        return render(request, self.template_name, {'user_email': user.email})

    def _limpiar_sesion_2fa(self, request):
        for key in ('2fa_user_id', '2fa_codigo', '2fa_expira', '2fa_intentos'):
            request.session.pop(key, None)


def resend_2fa(request):
    """Reenvía un código nuevo sin tener que volver a escribir usuario/contraseña."""
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        messages.error(request, 'Tu sesión de verificación expiró. Inicia sesión de nuevo.')
        return redirect('security:login')

    user = get_object_or_404(User, pk=user_id)
    codigo = f'{random.randint(0, 999999):06d}'
    request.session['2fa_codigo'] = codigo
    request.session['2fa_expira'] = (timezone.now() + timedelta(minutes=10)).isoformat()
    request.session['2fa_intentos'] = 0

    ok, msg = send_2fa_code_email(user, codigo)
    if ok:
        messages.info(request, f'Enviamos un nuevo código a {user.email}.')
    else:
        messages.error(request, f'No se pudo reenviar el código: {msg}')
    return redirect('security:verify_2fa')


class SecurityLogoutView(LogoutView):
    """Logout con CBV. Redirige según LOGOUT_REDIRECT_URL."""
    pass

# === USUARIOS (solo Administrador) ===
class UserCreateView(AdminOnlyMixin, PermissionOrRedirectMixin, CreateView):
    permission_required = 'auth.add_user'
    """Alta de usuarios. Solo accesible por el rol Administrador."""
    model = User
    form_class = AdminUserCreateForm
    template_name = 'security/user_create_form.html'
    success_url = reverse_lazy('security:user_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        activation_path = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        activation_url = self.request.build_absolute_uri(activation_path)

        sent, info_message = send_user_activation_email(user, activation_url)
        if sent:
            messages.success(self.request, f'Usuario creado correctamente. {info_message}')
        else:
            messages.warning(
                self.request,
                f'Usuario creado correctamente, pero no se pudo enviar el correo: {info_message}'
            )
        return response

class UserListView(AdminOnlyMixin, ExportMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'auth.view_user'
    model = User
    template_name = 'security/user_list.html'
    context_object_name = 'items'
    export_filename = 'usuarios'
    export_fields = [
        ('username', 'Usuario'),
        ('first_name', 'Nombres'),
        ('last_name', 'Apellidos'),
        ('email', 'Correo'),
        ('groups', 'Roles'),
        ('is_active', 'Estado'),
    ]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('groups')
        p = self.request.GET
        if p.get('username'):
            qs = qs.filter(username__icontains=p['username'])
        if p.get('email'):
            qs = qs.filter(email__icontains=p['email'])
        if p.get('group'):
            qs = qs.filter(groups__id=p['group'])
        is_active = p.get('is_active', '')
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        ctx['groups_catalog'] = Group.objects.order_by('name')
        filter_keys = ['username', 'email', 'group', 'is_active']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        return ctx

class UserUpdateView(AdminOnlyMixin, PermissionOrRedirectMixin, UpdateView):
    permission_required = 'auth.change_user'
    model = User
    form_class = UserUpdateForm
    template_name = 'security/user_form.html'
    success_url = reverse_lazy('security:user_list')

class UserDeleteView(AdminOnlyMixin, PermissionOrRedirectMixin, DeleteView):
    permission_required = 'auth.delete_user'
    model = User
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:user_list')

# === ROLES / GROUP (solo Administrador) ===
class GroupListView(AdminOnlyMixin, ExportMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'auth.view_group'
    model = Group
    template_name = 'security/group_list.html'
    context_object_name = 'items'
    export_filename = 'roles'
    export_fields = [
        ('name', 'Nombre del Rol'),
        ('permissions_count', 'Permisos Asignados'),
        ('users_count', 'Usuarios'),
    ]

    def get_queryset(self):
        qs = super().get_queryset().annotate(
            permissions_count=Count('permissions', distinct=True),
            users_count=Count('user', distinct=True),
        )
        name = self.request.GET.get('name')
        if name:
            qs = qs.filter(name__icontains=name)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        ctx['has_active_filters'] = bool(self.request.GET.get('name'))
        return ctx
   
   
    
# === TRADUCCIÓN Y ORGANIZACIÓN DE PERMISOS PARA LA UI DE ROLES ===
# Django genera los permisos automáticamente en inglés ("Can add product").
# Estos diccionarios permiten mostrar en el formulario de roles una matriz
# entendible en español: Módulo -> Recurso -> Acción (Ver/Crear/Editar/Eliminar),
# en vez de una lista plana de checkboxes con nombres técnicos.

APP_SECTION_META = {
    'billing':    ('Facturación y Catálogo',     'bi-shop',                         'Marcas, catálogo de productos, clientes y facturación de ventas.'),
    'purchasing': ('Compras',                     'bi-cart-fill',                    'Registro y control de compras a proveedores.'),
    'cobros':     ('Cobros (Cuentas por Cobrar)', 'bi-cash-coin',                    'Abonos y pagos recibidos de clientes por facturas a crédito.'),
    'pagos':      ('Pagos (Cuentas por Pagar)',   'bi-credit-card-fill',             'Abonos y pagos realizados a proveedores por compras a crédito.'),
    'auth':       ('Usuarios y Roles',            'bi-people-fill',                  'Creación y administración de usuarios, roles y permisos del sistema.'),
    'security':   ('Exportación de Reportes',     'bi-file-earmark-arrow-down-fill', 'Permite exportar los listados del sistema a PDF o Excel.'),
}

MODEL_LABELS_ES = {
    ('billing', 'brand'):            ('Marcas',                 'bi-tags-fill',         'Marcas de los productos del catálogo.'),
    ('billing', 'productgroup'):     ('Grupos de Productos',    'bi-collection-fill',   'Categorías para organizar los productos.'),
    ('billing', 'supplier'):         ('Proveedores',            'bi-truck',             'Empresas que suministran los productos.'),
    ('billing', 'product'):         ('Productos',              'bi-box-seam-fill',     'Catálogo de productos a la venta.'),
    ('billing', 'customer'):         ('Clientes',               'bi-person-vcard-fill', 'Clientes registrados en el sistema.'),
    ('billing', 'customerprofile'):  ('Perfiles de Cliente',    'bi-person-badge-fill', 'Información adicional del cliente.'),
    ('billing', 'invoice'):          ('Facturas',               'bi-receipt',           'Facturas de venta emitidas a clientes.'),
    ('billing', 'invoicedetail'):    ('Detalles de Factura',    'bi-list-ul',           'Líneas de producto dentro de una factura.'),
    ('purchasing', 'purchase'):      ('Compras',                'bi-cart-fill',         'Compras registradas a proveedores.'),
    ('purchasing', 'purchasedetail'): ('Detalles de Compra',    'bi-list-ul',           'Líneas de producto dentro de una compra.'),
    ('cobros', 'cobrofactura'):      ('Cobros de Facturas',     'bi-cash-coin',         'Abonos registrados sobre facturas a crédito.'),
    ('pagos', 'pagocompra'):         ('Pagos a Proveedores',    'bi-credit-card-fill',  'Abonos registrados sobre compras a crédito.'),
    ('auth', 'user'):                ('Usuarios',               'bi-people-fill',       'Cuentas de acceso al sistema.'),
    ('auth', 'group'):               ('Roles',                  'bi-shield-lock-fill',  'Roles y los permisos que tienen asignados.'),
    ('auth', 'permission'):          ('Permisos',                'bi-key-fill',          'Catálogo de permisos disponibles.'),
}

ACTION_LABELS_ES = {
    'view':   ('Ver',      'bi-eye-fill'),
    'add':    ('Crear',    'bi-plus-lg'),
    'change': ('Editar',   'bi-pencil-fill'),
    'delete': ('Eliminar', 'bi-trash-fill'),
}

EXTRA_PERMISSION_ICONS = {
    'export_pdf': 'bi-file-earmark-pdf-fill',
    'export_excel': 'bi-file-earmark-excel-fill',
}


def build_permission_matrix(form):
    """
    Convierte el campo `permissions` del GroupForm en una estructura
    Módulo -> Recurso -> {Ver, Crear, Editar, Eliminar} lista para pintar
    como una matriz de checkboxes, en vez de una lista plana en inglés.
    Los permisos que no siguen el patrón CRUD estándar (ej. export_pdf)
    se listan aparte, en la sección "extra" de su módulo.
    """
    perms_qs = form.fields['permissions'].queryset
    checkboxes = list(form['permissions'])

    apps = {}
    for perm, checkbox in zip(perms_qs, checkboxes):
        app_label = perm.content_type.app_label
        model = perm.content_type.model
        section_label, section_icon, section_desc = APP_SECTION_META.get(
            app_label, (app_label.title(), 'bi-folder-fill', '')
        )
        app_entry = apps.setdefault(app_label, {
            'label': section_label,
            'icon': section_icon,
            'description': section_desc,
            'models': {},
            'extra': [],
        })

        action, sep, rest = perm.codename.partition('_')
        if sep and action in ACTION_LABELS_ES and rest:
            model_label, model_icon, model_hint = MODEL_LABELS_ES.get(
                (app_label, model), (model.replace('_', ' ').title(), 'bi-folder-fill', '')
            )
            model_entry = app_entry['models'].setdefault(model, {
                'label': model_label,
                'icon': model_icon,
                'hint': model_hint,
                'actions': {},
            })
            model_entry['actions'][action] = checkbox
        else:
            app_entry['extra'].append({
                'checkbox': checkbox,
                'icon': EXTRA_PERMISSION_ICONS.get(perm.codename, 'bi-star-fill'),
            })

    sections = []
    for data in apps.values():
        models = sorted(data['models'].values(), key=lambda m: m['label'])
        total = sum(len(m['actions']) for m in models) + len(data['extra'])
        sections.append({
            'label': data['label'],
            'icon': data['icon'],
            'description': data['description'],
            'models': models,
            'extra': data['extra'],
            'count': total,
        })
    sections.sort(key=lambda s: s['label'])
    return sections


class GroupCreateView(AdminOnlyMixin, PermissionOrRedirectMixin, CreateView):
    permission_required = 'auth.add_group'
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['permission_matrix'] = build_permission_matrix(ctx['form'])
        return ctx

class GroupUpdateView(AdminOnlyMixin, PermissionOrRedirectMixin, UpdateView):
    permission_required = 'auth.change_group'
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['permission_matrix'] = build_permission_matrix(ctx['form'])
        return ctx

class GroupDeleteView(AdminOnlyMixin, PermissionOrRedirectMixin, DeleteView):
    permission_required = 'auth.delete_group'
    model = Group
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:group_list')

# === PERMISOS / PERMISSION (solo Administrador) ===
class PermissionListView(AdminOnlyMixin, ExportMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'auth.view_permission'
    model = Permission
    template_name = 'security/permission_list.html'
    context_object_name = 'items'
    export_filename = 'permisos'
    export_fields = [
        ('name', 'Nombre'),
        ('codename', 'Codename'),
        ('content_type.app_label', 'Aplicación'),
        ('content_type.model', 'Modelo'),
    ]

    def get_queryset(self):
        qs = Permission.objects.select_related('content_type')
        p = self.request.GET
        if p.get('name'):
            qs = qs.filter(Q(name__icontains=p['name']) | Q(codename__icontains=p['name']))
        if p.get('app_label'):
            qs = qs.filter(content_type__app_label=p['app_label'])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        ctx['app_labels'] = Permission.objects.select_related('content_type').values_list(
            'content_type__app_label', flat=True
        ).distinct().order_by('content_type__app_label')
        filter_keys = ['name', 'app_label']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        return ctx

class PermissionCreateView(AdminOnlyMixin, PermissionOrRedirectMixin, CreateView):
    permission_required = 'auth.add_permission'
    model = Permission
    form_class = PermissionForm
    template_name = 'security/permission_form.html'
    success_url = reverse_lazy('security:permission_list')

class PermissionUpdateView(AdminOnlyMixin, PermissionOrRedirectMixin, UpdateView):
    permission_required = 'auth.change_permission'
    model = Permission
    form_class = PermissionForm
    template_name = 'security/permission_form.html'
    success_url = reverse_lazy('security:permission_list')

class PermissionDeleteView(AdminOnlyMixin, PermissionOrRedirectMixin, DeleteView):
    permission_required = 'auth.delete_permission'
    model = Permission
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:permission_list')
