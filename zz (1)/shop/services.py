"""Business/services layer cho ứng dụng shop.

Tệp này gom các quy tắc nghiệp vụ chính để view mỏng hơn:
- seed dữ liệu mẫu
- lọc / sắp xếp danh sách
- quy tắc chuyển trạng thái đơn hàng
- tính tổng tiền và tạo đơn
"""

from __future__ import annotations

from typing import Iterable

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import DonHang, SanPham, Wallet, WalletTransaction


PRODUCT_SORTS = {
    "newest": ("-id",),
    "oldest": ("id",),
    "name_asc": ("ten", "id"),
    "name_desc": ("-ten", "-id"),
    "price_asc": ("gia", "id"),
    "price_desc": ("-gia", "-id"),
    "loai_asc": ("loai", "id"),
    "loai_desc": ("-loai", "-id"),
}

ORDER_SORTS = {
    "newest": ("-id",),
    "oldest": ("id",),
    "total_asc": ("tong_tien", "id"),
    "total_desc": ("-tong_tien", "-id"),
    "status_asc": ("trang_thai", "-id"),
    "status_desc": ("-trang_thai", "-id"),
}

USER_SORTS = {
    "newest": ("-date_joined", "-id"),
    "oldest": ("date_joined", "id"),
    "name_asc": ("username", "id"),
    "name_desc": ("-username", "-id"),
}

# Quy tắc chuyển trạng thái. Admin có quyền rộng hơn User.
ORDER_TRANSITIONS = {
    "user": {
        "Pending": {"Confirmed", "Cancelled"},
        "Confirmed": {"Cancelled"},
        "Approved": set(),
        "Rejected": set(),
        "Cancelled": set(),
    },
    "admin": {
        "Pending": {"Confirmed", "Approved", "Rejected", "Cancelled"},
        "Confirmed": {"Approved", "Rejected", "Cancelled"},
        "Approved": set(),
        "Rejected": set(),
        "Cancelled": set(),
    },
}


def seed_sample_products() -> None:
    """Tạo dữ liệu mẫu nếu chưa có để người dùng có ngay nội dung demo."""

    ds = [
        {
            "ten": "Lắc tay Vàng 99% 0000Y004602",
            "gia": 22_130_000,
            "anh": "sanpham/lac_tay_9999.png",
        },
        {
            "ten": "Mặt dây chuyền Vàng trắng 41,6% (10K) Đính đá ECZ XMXMW003560",
            "gia": 3_990_405,
            "anh": "sanpham/mat_day_ecz.png",
        },
    ]

    for item in ds:
        SanPham.objects.get_or_create(
            ten=item["ten"],
            defaults={
                "gia": item["gia"],
                "anh": item["anh"],
                "trang_thai": "active",
            },
        )


def get_user_role(user) -> str:
    """Phân vai trò theo đúng yêu cầu Guest/User/Admin."""

    if not getattr(user, "is_authenticated", False):
        return "guest"
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return "admin"
    return "user"


def calculate_order_total(product: SanPham, quantity: int) -> int:
    return int(product.gia) * int(quantity)


def get_or_create_wallet(user: User) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def create_order_from_checkout(*, user: User, product: SanPham, cleaned_data: dict) -> DonHang:
    """Tạo đơn từ form checkout của người dùng."""

    so_luong = int(cleaned_data["so_luong"])
    tong_tien = calculate_order_total(product, so_luong)
    phuong_thuc_tt = cleaned_data["phuong_thuc_tt"]

    if phuong_thuc_tt == "ViDienTu":
        wallet = get_or_create_wallet(user)
        if wallet.balance < tong_tien:
            raise ValidationError("Số dư ví không đủ để thanh toán đơn hàng này.")

        wallet.balance -= tong_tien
        wallet.save(update_fields=["balance", "updated_at"])
    else:
        wallet = None

    order = DonHang.objects.create(
        nguoi_dat=user,
        san_pham=product,
        ho_ten=cleaned_data["ho_ten"],
        sdt=cleaned_data["sdt"],
        dia_chi=cleaned_data["dia_chi"],
        ghi_chu=cleaned_data.get("ghi_chu", ""),
        phuong_thuc_tt=phuong_thuc_tt,
        so_luong=so_luong,
        tong_tien=tong_tien,
        trang_thai="Pending",
    )

    if wallet is not None:
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=tong_tien,
            transaction_type="payment",
            order=order,
            note=f"Thanh toán đơn hàng #{order.id}",
        )

    return order


def can_transition(current_status: str, new_status: str, actor_role: str) -> bool:
    if current_status == new_status:
        return True
    role_key = "admin" if actor_role == "admin" else "user"
    allowed = ORDER_TRANSITIONS.get(role_key, {}).get(current_status, set())
    return new_status in allowed



def get_allowed_statuses(order: DonHang, actor_role: str, *, include_current: bool = True) -> list[tuple[str, str]]:
    """Trả về danh sách trạng thái hợp lệ cho order theo vai trò."""

    allowed_codes: Iterable[str] = ORDER_TRANSITIONS.get(
        "admin" if actor_role == "admin" else "user", {}
    ).get(order.trang_thai, set())

    choices = []
    for code, label in DonHang.TRANG_THAI:
        if code == order.trang_thai and include_current:
            choices.append((code, label))
        elif code in allowed_codes:
            choices.append((code, label))
    return choices


@transaction.atomic
def update_order_status(*, order: DonHang, new_status: str, actor_role: str) -> tuple[bool, str]:
    """Đổi trạng thái nếu hợp lệ, trả về (thành công?, thông báo)."""

    valid_codes = {code for code, _ in DonHang.TRANG_THAI}
    if new_status not in valid_codes:
        return False, "Trạng thái không hợp lệ."

    if order.trang_thai == new_status:
        return True, "Trạng thái đơn hàng không thay đổi."

    if not can_transition(order.trang_thai, new_status, actor_role):
        return False, f"Không thể chuyển từ {order.trang_thai} sang {new_status}."

    order.trang_thai = new_status

    if (
        order.phuong_thuc_tt == "ViDienTu"
        and new_status in {"Cancelled", "Rejected"}
        and not order.da_hoan_tien
    ):
        wallet = get_or_create_wallet(order.nguoi_dat)
        wallet.balance += order.tong_tien
        wallet.save(update_fields=["balance", "updated_at"])
        order.da_hoan_tien = True
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=order.tong_tien,
            transaction_type="refund",
            order=order,
            note=f"Hoàn tiền cho đơn hàng #{order.id}",
        )
        refund_suffix = " Đã hoàn tiền vào ví điện tử."
    else:
        refund_suffix = ""

    order.save(update_fields=["trang_thai", "da_hoan_tien"])
    return True, f"Đã cập nhật trạng thái đơn #{order.id} thành {order.get_trang_thai_display()}.{refund_suffix}"



def apply_product_filters(queryset, *, q: str = "", status: str = "", loai: str = "", sort: str = "newest"):
    if q:
        queryset = queryset.filter(ten__icontains=q)
    if status in {code for code, _ in SanPham.TRANG_THAI}:
        queryset = queryset.filter(trang_thai=status)
    if loai in {code for code, _ in SanPham.LOAI_SAN_PHAM}:
        queryset = queryset.filter(loai=loai)
    return queryset.order_by(*PRODUCT_SORTS.get(sort, PRODUCT_SORTS["newest"]))



def apply_order_filters(queryset, *, q: str = "", status: str = "", payment: str = "", sort: str = "newest"):
    if status in {code for code, _ in DonHang.TRANG_THAI}:
        queryset = queryset.filter(trang_thai=status)
    if payment in {code for code, _ in DonHang.PHUONG_THUC_TT}:
        queryset = queryset.filter(phuong_thuc_tt=payment)
    if q:
        queryset = queryset.filter(
            models.Q(nguoi_dat__username__icontains=q)
            | models.Q(ho_ten__icontains=q)
            | models.Q(sdt__icontains=q)
            | models.Q(san_pham__ten__icontains=q)
            | models.Q(dia_chi__icontains=q)
        )
    return queryset.order_by(*ORDER_SORTS.get(sort, ORDER_SORTS["newest"]))



def apply_user_filters(queryset, *, q: str = "", role: str = "", active: str = "", sort: str = "newest"):
    if q:
        queryset = queryset.filter(
            models.Q(username__icontains=q) | models.Q(email__icontains=q)
        )
    if role == "admin":
        queryset = queryset.filter(is_staff=True)
    elif role == "user":
        queryset = queryset.filter(is_staff=False)

    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)

    return queryset.order_by(*USER_SORTS.get(sort, USER_SORTS["newest"]))
