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

from shared.mixins import GroupRequiredMixin, PermissionOrRedirectMixin
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

class UserListView(AdminOnlyMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'auth.view_user'
    model = User
    template_name = 'security/user_list.html'
    context_object_name = 'items'

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
class GroupListView(AdminOnlyMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'auth.view_group'
    model = Group
    template_name = 'security/group_list.html'
    context_object_name = 'items'
   
   
    
APP_LABELS_ES = {
'billing': 'Facturación y Catálogo',
'cobros': 'Cobros (Cuentas por Cobrar)',
'pagos': 'Pagos (Cuentas por Pagar)',
'purchasing': 'Compras',
'auth': 'Usuarios y Roles',
}

class GroupCreateView(AdminOnlyMixin, PermissionOrRedirectMixin, CreateView):
    permission_required = 'auth.add_group'
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx['form']
        perms_qs = form.fields['permissions'].queryset
        checkboxes = list(form['permissions'])

        grouped = {}
        for perm, checkbox in zip(perms_qs, checkboxes):
            label = APP_LABELS_ES.get(perm.content_type.app_label, perm.content_type.app_label.title())
            grouped.setdefault(label, []).append(checkbox)

        ctx['grouped_permissions'] = grouped
        return ctx

class GroupUpdateView(AdminOnlyMixin, PermissionOrRedirectMixin, UpdateView):
    permission_required = 'auth.change_group'
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx['form']
        perms_qs = form.fields['permissions'].queryset
        checkboxes = list(form['permissions'])

        grouped = {}
        for perm, checkbox in zip(perms_qs, checkboxes):
            label = APP_LABELS_ES.get(perm.content_type.app_label, perm.content_type.app_label.title())
            grouped.setdefault(label, []).append(checkbox)

        ctx['grouped_permissions'] = grouped
        return ctx

class GroupDeleteView(AdminOnlyMixin, PermissionOrRedirectMixin, DeleteView):
    permission_required = 'auth.delete_group'
    model = Group
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:group_list')

# === PERMISOS / PERMISSION (solo Administrador) ===
class PermissionListView(AdminOnlyMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'auth.view_permission'
    model = Permission
    template_name = 'security/permission_list.html'
    context_object_name = 'items'
    queryset = Permission.objects.select_related('content_type')

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
