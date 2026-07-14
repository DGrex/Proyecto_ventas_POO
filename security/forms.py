from django import forms
from django.contrib.auth.models import User, Group, Permission

# === 1. CREACIÓN DE USUARIO (SOLO ADMINISTRADOR) ===
class AdminUserCreateForm(forms.ModelForm):
    """
    Creación de usuarios. NO es un registro público: solo puede
    usarse desde una vista protegida con AdminOnlyMixin.

    El Administrador NO define la contraseña: el usuario la crea él
    mismo desde un enlace de activación que se le envía por correo
    (mismo mecanismo de "recuperar contraseña" de Django).
    El Administrador asigna el/los rol(es) directamente al crear la cuenta.
    """
    email = forms.EmailField(required=True)
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Roles',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email',
                  'groups', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields:
            if f == 'is_active':
                self.fields[f].widget.attrs['class'] = 'form-check-input'
            elif f != 'groups':
                self.fields[f].widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        user = super().save(commit=False)
        # Sin contraseña utilizable hasta que el usuario la defina desde
        # el enlace de activación que recibe por correo.
        user.set_unusable_password()
        if commit:
            user.save()
            user.groups.set(self.cleaned_data['groups'])
        return user

# === 2. EDICIÓN DE USUARIO (asignar roles) ===
class UserUpdateForm(forms.ModelForm):
    """El Administrador edita datos y roles de un usuario."""
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Roles',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email',
                  'is_active', 'groups']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# === 3. ROLES (Group) CON SUS PERMISOS ===
class GroupForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').exclude(
            content_type__app_label__in=['admin', 'contenttypes', 'sessions']
        ).order_by('content_type__app_label', 'content_type__model', 'codename'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Permisos',
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
# === 4. PERMISOS PERSONALIZADOS ===
class PermissionForm(forms.ModelForm):
    """Crear un permiso propio, ej: can_approve_invoice."""
    class Meta:
        model = Permission
        fields = ['name', 'codename', 'content_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'codename': forms.TextInput(attrs={'class': 'form-control'}),
            'content_type': forms.Select(attrs={'class': 'form-select'}),
        }

