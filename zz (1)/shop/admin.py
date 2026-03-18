from django.contrib import admin

from .models import DonHang, SanPham, Wallet, WalletTransaction


@admin.register(SanPham)
class SanPhamAdmin(admin.ModelAdmin):
    list_display = ("id", "ten", "gia", "trang_thai")
    list_filter = ("trang_thai",)
    search_fields = ("ten",)
    ordering = ("-id",)


@admin.register(DonHang)
class DonHangAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nguoi_dat",
        "san_pham",
        "so_luong",
        "tong_tien",
        "trang_thai",
        "phuong_thuc_tt",
        "tao_luc",
    )
    list_filter = ("trang_thai", "phuong_thuc_tt", "tao_luc")
    search_fields = (
        "nguoi_dat__username",
        "san_pham__ten",
        "ho_ten",
        "sdt",
        "dia_chi",
    )
    ordering = ("-id",)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "balance", "updated_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-updated_at",)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "transaction_type", "amount", "order", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("wallet__user__username", "note")
    ordering = ("-created_at", "-id")
