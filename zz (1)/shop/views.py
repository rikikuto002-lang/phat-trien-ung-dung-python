import datetime as dt

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import admin_required
from .forms import AdminDonHangForm, AdminUserForm, DatHangForm, SanPhamForm
from .models import DonHang, SanPham, WalletTransaction
from .services import (
    ORDER_SORTS,
    PRODUCT_SORTS,
    USER_SORTS,
    apply_order_filters,
    apply_product_filters,
    apply_user_filters,
    create_order_from_checkout,
    get_allowed_statuses,
    get_or_create_wallet,
    get_user_role,
    seed_sample_products,
    update_order_status,
)


PRODUCT_SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("oldest", "Cũ nhất"),
    ("name_asc", "Tên A-Z"),
    ("name_desc", "Tên Z-A"),
    ("price_asc", "Giá tăng dần"),
    ("price_desc", "Giá giảm dần"),
    ("loai_asc", "Loại A-Z"),
    ("loai_desc", "Loại Z-A"),
]

ORDER_SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("oldest", "Cũ nhất"),
    ("total_desc", "Tổng tiền giảm dần"),
    ("total_asc", "Tổng tiền tăng dần"),
    ("status_asc", "Trạng thái A-Z"),
]

USER_SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("oldest", "Cũ nhất"),
    ("name_asc", "Username A-Z"),
    ("name_desc", "Username Z-A"),
]


def home(request):
    """Trang chủ: hiển thị sản phẩm active + search/sort."""

    seed_sample_products()
    q = request.GET.get("q", "").strip()
    loai = request.GET.get("loai", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if sort not in PRODUCT_SORTS:
        sort = "newest"

    ds = apply_product_filters(
        SanPham.objects.filter(trang_thai="active"),
        q=q,
        loai=loai,
        sort=sort,
    )

    return render(
        request,
        "home.html",
        {
            "ds": ds,
            "q": q,
            "loai": loai,
            "sort": sort,
            "product_sort_choices": PRODUCT_SORT_CHOICES,
            "loai_choices": SanPham.LOAI_SAN_PHAM,
        },
    )



def dang_ky(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        password2 = request.POST.get("password2", "").strip()

        if not username or not password:
            return render(request, "dang_ky.html", {"loi": "Nhập tên đăng nhập và mật khẩu."})

        if password != password2:
            return render(request, "dang_ky.html", {"loi": "Mật khẩu nhập lại không khớp."})

        if User.objects.filter(username=username).exists():
            return render(request, "dang_ky.html", {"loi": "Tên đăng nhập đã tồn tại."})

        User.objects.create_user(username=username, email=email, password=password)
        messages.success(request, "Đăng ký thành công. Bạn có thể đăng nhập ngay bây giờ.")
        return redirect("dang_nhap")

    return render(request, "dang_ky.html")



def dang_nhap(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is None:
            user_obj = User.objects.filter(username=username).first()
            if user_obj and not user_obj.is_active:
                return render(request, "dang_nhap.html", {"loi": "Tài khoản đang bị khóa (inactive)."})
            return render(request, "dang_nhap.html", {"loi": "Sai tên đăng nhập hoặc mật khẩu."})

        login(request, user)
        messages.success(request, f"Đăng nhập thành công với vai trò {get_user_role(user).title()}.")
        return redirect("home")

    return render(request, "dang_nhap.html")



def dang_xuat(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "Bạn đã đăng xuất.")
    return redirect("home")


@login_required
def dat_hang(request, san_pham_id):
    seed_sample_products()
    sp = get_object_or_404(SanPham, id=san_pham_id)

    if not sp.co_the_dat_hang and not request.user.is_staff:
        messages.error(request, "Sản phẩm này đang inactive nên không thể đặt hàng.")
        return redirect("home")

    initial = {
        "ho_ten": request.user.get_full_name() or request.user.username,
        "so_luong": 1,
        "phuong_thuc_tt": "COD",
    }
    form = DatHangForm(request.POST or None, initial=initial if request.method == "GET" else None)
    wallet = get_or_create_wallet(request.user)

    if request.method == "POST" and form.is_valid():
        try:
            don = create_order_from_checkout(
                user=request.user,
                product=sp,
                cleaned_data=form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message if hasattr(exc, "message") else str(exc))
        else:
            messages.success(request, f"Đặt hàng thành công. Mã đơn của bạn là #{don.id}.")
            return redirect("ds_don")

    return render(request, "dat_hang.html", {"sp": sp, "form": form, "wallet": wallet})




@login_required
def wallet_view(request):
    wallet = get_or_create_wallet(request.user)
    transactions = WalletTransaction.objects.filter(wallet=wallet).select_related("order").order_by("-created_at", "-id")
    return render(request, "wallet.html", {"wallet": wallet, "transactions": transactions})


@login_required
def wallet_deposit(request):
    wallet = get_or_create_wallet(request.user)
    if request.method == "POST":
        try:
            amount = int((request.POST.get("amount") or "0").strip())
        except ValueError:
            amount = 0

        if amount <= 0:
            messages.error(request, "Số tiền nạp phải lớn hơn 0.")
        else:
            wallet.balance += amount
            wallet.save(update_fields=["balance", "updated_at"])
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type="deposit",
                note="Nạp tiền vào ví điện tử",
            )
            messages.success(request, f"Nạp {amount:,} VND vào ví thành công.")
    return redirect("wallet")


@login_required
def ds_don(request):
    q = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if sort not in ORDER_SORTS:
        sort = "newest"

    ds = apply_order_filters(
        DonHang.objects.filter(nguoi_dat=request.user).select_related("san_pham"),
        q=q,
        status=trang_thai,
        sort=sort,
    )

    return render(
        request,
        "don_hang.html",
        {
            "ds": ds,
            "q": q,
            "trang_thai": trang_thai,
            "sort": sort,
            "sort_choices": ORDER_SORT_CHOICES,
            "trang_thai_choices": DonHang.TRANG_THAI,
        },
    )


@login_required
def xac_nhan_don(request, don_id):
    don = get_object_or_404(DonHang, id=don_id, nguoi_dat=request.user)
    ok, message = update_order_status(order=don, new_status="Confirmed", actor_role="user")
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("ds_don")


@login_required
def huy_don(request, don_id):
    don = get_object_or_404(DonHang, id=don_id, nguoi_dat=request.user)
    ok, message = update_order_status(order=don, new_status="Cancelled", actor_role="user")
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("ds_don")


# ===== Legacy URLs giữ tương thích với bản cũ =====
@admin_required
def ds_don_admin(request):
    return redirect("admin_donhang_list")


@admin_required
def duyet_don(request, don_id, hanh_dong):
    don = get_object_or_404(DonHang, id=don_id)
    new_status = "Approved" if hanh_dong == "approve" else "Rejected"
    ok, message = update_order_status(order=don, new_status=new_status, actor_role="admin")
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("admin_donhang_list")


# ===== Admin Panel =====
@admin_required
def admin_dashboard(request):
    tong_sp = SanPham.objects.count()
    tong_sp_active = SanPham.objects.filter(trang_thai="active").count()
    tong_sp_inactive = SanPham.objects.filter(trang_thai="inactive").count()
    tong_don = DonHang.objects.count()
    cho_xac_nhan = DonHang.objects.filter(trang_thai="Pending").count()
    da_duyet = DonHang.objects.filter(trang_thai="Approved").count()
    da_huy = DonHang.objects.filter(trang_thai="Cancelled").count()

    status_rows = DonHang.objects.values("trang_thai").annotate(c=Count("id")).order_by("trang_thai")
    status_labels = [r["trang_thai"] for r in status_rows]
    status_counts = [r["c"] for r in status_rows]

    today = timezone.localdate()
    start = today - dt.timedelta(days=6)
    daily_rows = (
        DonHang.objects.filter(tao_luc__date__gte=start, tao_luc__date__lte=today)
        .annotate(d=TruncDate("tao_luc"))
        .values("d")
        .annotate(orders=Count("id"), revenue=Sum("tong_tien"))
        .order_by("d")
    )
    daily_map = {r["d"]: r for r in daily_rows}
    days = [start + dt.timedelta(days=i) for i in range(7)]
    daily_labels = [d.strftime("%d/%m") for d in days]
    daily_orders = [int(daily_map.get(d, {}).get("orders") or 0) for d in days]
    daily_revenue = [int(daily_map.get(d, {}).get("revenue") or 0) for d in days]

    top_products = DonHang.objects.filter(san_pham__trang_thai="active").values("san_pham__ten").annotate(c=Count("id")).order_by("-c")[:10]

    return render(
        request,
        "admin_dashboard.html",
        {
            "tong_sp": tong_sp,
            "tong_sp_active": tong_sp_active,
            "tong_sp_inactive": tong_sp_inactive,
            "tong_don": tong_don,
            "cho_xac_nhan": cho_xac_nhan,
            "da_duyet": da_duyet,
            "da_huy": da_huy,
            "status_labels": status_labels,
            "status_counts": status_counts,
            "daily_labels": daily_labels,
            "daily_orders": daily_orders,
            "daily_revenue": daily_revenue,
            "top_products": top_products,
        },
    )


@admin_required
def admin_sanpham_list(request):
    q = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    loai = request.GET.get("loai", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if sort not in PRODUCT_SORTS:
        sort = "newest"

    ds = apply_product_filters(SanPham.objects.all(), q=q, status=trang_thai, loai=loai, sort=sort)
    return render(
        request,
        "admin_sanpham_list.html",
        {
            "ds": ds,
            "q": q,
            "trang_thai": trang_thai,
            "loai": loai,
            "sort": sort,
            "sort_choices": PRODUCT_SORT_CHOICES,
            "trang_thai_choices": SanPham.TRANG_THAI,
            "loai_choices": SanPham.LOAI_SAN_PHAM,
        },
    )


@admin_required
def admin_sanpham_detail(request, sp_id):
    sp = get_object_or_404(SanPham, id=sp_id)
    return render(request, "admin_sanpham_detail.html", {"sp": sp})


@admin_required
def admin_sanpham_create(request):
    form = SanPhamForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        sp = form.save()
        messages.success(request, f"Đã thêm sản phẩm #{sp.id} thành công.")
        return redirect("admin_sanpham_detail", sp_id=sp.id)
    return render(request, "admin_sanpham_form.html", {"mode": "create", "form": form})


@admin_required
def admin_sanpham_edit(request, sp_id):
    sp = get_object_or_404(SanPham, id=sp_id)
    form = SanPhamForm(request.POST or None, request.FILES or None, instance=sp)
    if request.method == "POST" and form.is_valid():
        sp = form.save()
        messages.success(request, f"Đã cập nhật sản phẩm #{sp.id}.")
        return redirect("admin_sanpham_detail", sp_id=sp.id)
    return render(request, "admin_sanpham_form.html", {"sp": sp, "mode": "edit", "form": form})


@admin_required
def admin_sanpham_delete(request, sp_id):
    sp = get_object_or_404(SanPham, id=sp_id)

    if request.method == "POST":
        try:
            sp.delete()
            messages.success(request, "Đã xoá sản phẩm thành công.")
            return redirect("admin_sanpham_list")
        except ProtectedError:
            messages.error(
                request,
                "Không thể xoá sản phẩm đã phát sinh đơn hàng. Hãy chuyển trạng thái sang inactive để ngừng bán.",
            )
            return redirect("admin_sanpham_detail", sp_id=sp.id)

    return render(request, "admin_sanpham_delete.html", {"sp": sp})


@admin_required
def admin_donhang_list(request):
    trang_thai = request.GET.get("trang_thai", "").strip()
    q = request.GET.get("q", "").strip()
    payment = request.GET.get("payment", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if sort not in ORDER_SORTS:
        sort = "newest"

    ds = apply_order_filters(
        DonHang.objects.select_related("nguoi_dat", "san_pham").all(),
        q=q,
        status=trang_thai,
        payment=payment,
        sort=sort,
    )

    return render(
        request,
        "admin_donhang_list.html",
        {
            "ds": ds,
            "q": q,
            "trang_thai": trang_thai,
            "payment": payment,
            "sort": sort,
            "sort_choices": ORDER_SORT_CHOICES,
            "trang_thai_choices": DonHang.TRANG_THAI,
            "payment_choices": DonHang.PHUONG_THUC_TT,
        },
    )


@admin_required
def admin_donhang_detail(request, don_id):
    don = get_object_or_404(DonHang.objects.select_related("nguoi_dat", "san_pham"), id=don_id)
    return render(
        request,
        "admin_donhang_detail.html",
        {
            "don": don,
            "allowed_statuses": get_allowed_statuses(don, actor_role="admin"),
        },
    )


@admin_required
def admin_donhang_create(request):
    form = AdminDonHangForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        don = form.save()
        messages.success(request, f"Đã tạo đơn hàng #{don.id}.")
        return redirect("admin_donhang_detail", don_id=don.id)
    return render(request, "admin_donhang_form.html", {"mode": "create", "form": form})


@admin_required
def admin_donhang_edit(request, don_id):
    don = get_object_or_404(DonHang, id=don_id)
    form = AdminDonHangForm(request.POST or None, instance=don)
    if request.method == "POST" and form.is_valid():
        don = form.save()
        messages.success(request, f"Đã cập nhật đơn hàng #{don.id}.")
        return redirect("admin_donhang_detail", don_id=don.id)
    return render(request, "admin_donhang_form.html", {"mode": "edit", "form": form, "don": don})


@admin_required
def admin_donhang_delete(request, don_id):
    don = get_object_or_404(DonHang.objects.select_related("nguoi_dat", "san_pham"), id=don_id)
    if request.method == "POST":
        don.delete()
        messages.success(request, f"Đã xoá đơn hàng #{don.id}.")
        return redirect("admin_donhang_list")
    return render(request, "admin_donhang_delete.html", {"don": don})


@admin_required
def admin_donhang_update(request, don_id):
    don = get_object_or_404(DonHang, id=don_id)
    if request.method == "POST":
        new_status = request.POST.get("trang_thai", "").strip()
        ok, message = update_order_status(order=don, new_status=new_status, actor_role="admin")
        if ok:
            messages.success(request, message)
        else:
            messages.error(request, message)
    return redirect(request.META.get("HTTP_REFERER", "admin_donhang_list"))


@admin_required
def admin_user_list(request):
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    active = request.GET.get("active", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if sort not in USER_SORTS:
        sort = "newest"

    users = apply_user_filters(User.objects.all(), q=q, role=role, active=active, sort=sort)

    return render(
        request,
        "admin_user_list.html",
        {
            "users": users,
            "q": q,
            "role": role,
            "active": active,
            "sort": sort,
            "sort_choices": USER_SORT_CHOICES,
            "role_choices": [("user", "User"), ("admin", "Admin")],
        },
    )


@admin_required
def admin_user_create(request):
    form = AdminUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Đã tạo user {user.username}.")
        return redirect("admin_user_list")
    return render(request, "admin_user_form.html", {"mode": "create", "form": form})


@admin_required
def admin_user_edit(request, user_id):
    u = get_object_or_404(User, id=user_id)
    form = AdminUserForm(request.POST or None, instance=u)

    if request.method == "POST" and form.is_valid():
        if request.user == u and form.cleaned_data["role"] != "admin":
            form.add_error("role", "Bạn không thể tự hạ quyền chính mình xuống User.")
        if request.user == u and not form.cleaned_data["is_active"]:
            form.add_error("is_active", "Bạn không thể tự khóa tài khoản đang đăng nhập.")

        if not form.errors:
            password_changed = bool(form.cleaned_data.get("password"))
            saved_user = form.save()
            if request.user == u and password_changed:
                update_session_auth_hash(request, saved_user)
            messages.success(request, f"Đã cập nhật user {saved_user.username}.")
            return redirect("admin_user_list")

    return render(request, "admin_user_form.html", {"mode": "edit", "form": form, "u": u})


@admin_required
def admin_user_delete(request, user_id):
    u = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        if request.user == u:
            messages.error(request, "Bạn không thể xoá chính tài khoản đang đăng nhập.")
            return redirect("admin_user_list")
        if DonHang.objects.filter(nguoi_dat=u).exists():
            messages.error(request, "Không thể xoá user đã phát sinh đơn hàng.")
            return redirect("admin_user_list")

        username = u.username
        u.delete()
        messages.success(request, f"Đã xoá user {username}.")
        return redirect("admin_user_list")

    return render(request, "admin_user_delete.html", {"u": u})
