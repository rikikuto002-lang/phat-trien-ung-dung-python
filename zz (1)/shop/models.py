from django.contrib.auth.models import User
from django.db import models


class SanPham(models.Model):
    """Bảng sản phẩm chính."""

    TRANG_THAI = [
        ("active", "Hoạt động"),
        ("inactive", "Ngừng kinh doanh"),
    ]

    LOAI_SAN_PHAM = [
        ("bao_ve", "Bảo vệ"),
        ("nang_luong_sac", "Năng lượng & Sạc"),
        ("am_thanh", "Âm thanh"),
        ("ho_tro_luu_tru", "Hỗ trợ & Lưu trữ"),
        ("tien_ich_khac", "Tiện ích khác"),
    ]

    ten = models.CharField(max_length=100)
    gia = models.IntegerField(default=0)
    anh = models.ImageField(upload_to="sanpham/", blank=True, null=True, default="sanpham/banner.png")
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default="active")
    loai = models.CharField(max_length=20, choices=LOAI_SAN_PHAM, default="tien_ich_khac")

    def __str__(self):
        return self.ten

    @property
    def co_the_dat_hang(self) -> bool:
        return self.trang_thai == "active"


class Wallet(models.Model):
    """Ví điện tử cho mỗi người dùng."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ví - {self.user.username}"


class WalletTransaction(models.Model):
    """Lịch sử giao dịch ví."""

    TRANSACTION_TYPES = [
        ("deposit", "Nạp tiền"),
        ("payment", "Thanh toán đơn hàng"),
        ("refund", "Hoàn tiền"),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    order = models.ForeignKey("DonHang", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_transactions")
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.wallet.user.username} - {self.transaction_type} - {self.amount}"


class DonHang(models.Model):
    """Bảng đơn hàng chính."""

    TRANG_THAI = [
        ("Pending", "Chờ xác nhận"),
        ("Confirmed", "Đã xác nhận"),
        ("Cancelled", "Đã huỷ"),
        ("Approved", "Đã duyệt"),
        ("Rejected", "Từ chối"),
    ]

    PHUONG_THUC_TT = [
        ("COD", "COD (Thanh toán khi nhận hàng)"),
        ("ChuyenKhoan", "Chuyển khoản"),
        ("ViDienTu", "Ví điện tử"),
    ]

    nguoi_dat = models.ForeignKey(User, on_delete=models.CASCADE, related_name="don_hangs")
    san_pham = models.ForeignKey(SanPham, on_delete=models.PROTECT, related_name="don_hangs")

    ho_ten = models.CharField(max_length=100, default="")
    sdt = models.CharField(max_length=20, default="")
    dia_chi = models.CharField(max_length=255, default="")
    ghi_chu = models.CharField(max_length=255, blank=True, default="")
    phuong_thuc_tt = models.CharField(max_length=50, choices=PHUONG_THUC_TT, default="COD")

    so_luong = models.IntegerField(default=1)
    tong_tien = models.IntegerField(default=0)
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default="Pending")
    da_hoan_tien = models.BooleanField(default=False)
    tao_luc = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Don #{self.id} - {self.nguoi_dat.username}"

    def tinh_tong_tien(self) -> int:
        return max(int(self.so_luong or 0), 0) * max(int(self.san_pham.gia or 0), 0)

    def save(self, *args, **kwargs):
        # Tự đồng bộ tổng tiền để dữ liệu nhất quán dù tạo từ admin hay từ user.
        if self.san_pham_id:
            self.tong_tien = self.tinh_tong_tien()
        super().save(*args, **kwargs)


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_wallet_for_user(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)
