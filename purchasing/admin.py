from django.contrib import admin
from .models import Purchase, PurchaseDetail

class PurchaseDetailInline(admin.TabularInline):
    model = PurchaseDetail
    extra = 1

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'document_number', 'purchase_date', 'total', 'is_active')
    list_filter = ('supplier', 'purchase_date', 'is_active')
    search_fields = ('document_number', 'supplier__name')
    inlines = [PurchaseDetailInline]
