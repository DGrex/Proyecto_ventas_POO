from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from shared.mixins import GroupRequiredMixin
from shared.notifications import send_user_activation_email
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
    """Login con CBV. Reutiliza el template de la PARTE 9."""
    template_name = 'registration/login.html'

class SecurityLogoutView(LogoutView):
    """Logout con CBV. Redirige según LOGOUT_REDIRECT_URL."""
    pass

# === USUARIOS (solo Administrador) ===
class UserCreateView(AdminOnlyMixin, CreateView):
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

class UserListView(AdminOnlyMixin, ListView):
    model = User
    template_name = 'security/user_list.html'
    context_object_name = 'items'

class UserUpdateView(AdminOnlyMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'security/user_form.html'
    success_url = reverse_lazy('security:user_list')

class UserDeleteView(AdminOnlyMixin, DeleteView):
    model = User
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:user_list')

# === ROLES / GROUP (solo Administrador) ===
class GroupListView(AdminOnlyMixin, ListView):
    model = Group
    template_name = 'security/group_list.html'
    context_object_name = 'items'

class GroupCreateView(AdminOnlyMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

class GroupUpdateView(AdminOnlyMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

class GroupDeleteView(AdminOnlyMixin, DeleteView):
    model = Group
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:group_list')

# === PERMISOS / PERMISSION (solo Administrador) ===
class PermissionListView(AdminOnlyMixin, ListView):
    model = Permission
    template_name = 'security/permission_list.html'
    context_object_name = 'items'
    queryset = Permission.objects.select_related('content_type')

class PermissionCreateView(AdminOnlyMixin, CreateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'security/permission_form.html'
    success_url = reverse_lazy('security:permission_list')

class PermissionUpdateView(AdminOnlyMixin, UpdateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'security/permission_form.html'
    success_url = reverse_lazy('security:permission_list')

class PermissionDeleteView(AdminOnlyMixin, DeleteView):
    model = Permission
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:permission_list')
