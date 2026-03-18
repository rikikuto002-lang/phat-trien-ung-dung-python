"""Form layer: gom validate input, kiểm tra file upload và chuẩn hoá dữ liệu."""

from __future__ import annotations

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import DonHang, SanPham
from .services import calculate_order_total, can_transition


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB


class BaseStyledForm(forms.Form):
    """Form thường dùng class CSS chung."""

    def _apply_common_css(self):
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"input {css}".strip()


class SanPhamForm(forms.ModelForm):
    """Form cho CRUD sản phẩm, có validate ảnh upload."""

    anh = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"class": "input", "accept": ".jpg,.jpeg,.png,.webp,.gif,image/*"}))

    class Meta:
        model = SanPham
        fields = ["ten", "gia", "trang_thai", "loai", "anh"]
        widgets = {
            "ten": forms.TextInput(attrs={"class": "input", "placeholder": "Tên sản phẩm"}),
            "gia": forms.NumberInput(attrs={"class": "input", "min": "0", "placeholder": "Giá (VND)"}),
            "trang_thai": forms.Select(attrs={"class": "input"}),
            "loai": forms.Select(attrs={"class": "input"}),
        }

    def clean_gia(self):
        gia = self.cleaned_data["gia"]
        if gia is None or int(gia) < 0:
            raise ValidationError("Giá phải là số >= 0.")
        return gia

    def clean_anh(self):
        anh = self.cleaned_data.get("anh")
        if not anh:
            return anh

        ten_file = getattr(anh, "name", "")
        ext = ten_file.rsplit(".", 1)[-1].lower() if "." in ten_file else ""
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError("Chỉ cho phép ảnh JPG, JPEG, PNG, WEBP hoặc GIF.")

        if getattr(anh, "size", 0) > MAX_UPLOAD_SIZE:
            raise ValidationError("Ảnh vượt quá 2MB. Vui lòng chọn ảnh nhỏ hơn.")

        content_type = getattr(anh, "content_type", "")
        if content_type and not content_type.startswith("image/"):
            raise ValidationError("Tệp tải lên phải là ảnh hợp lệ.")
        return anh


class DatHangForm(BaseStyledForm):
    """Form checkout cho người dùng đặt hàng."""

    ho_ten = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: Trần Bình Minh"}))
    sdt = forms.CharField(max_length=20, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: 0987654321"}))
    dia_chi = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"placeholder": "Số nhà, đường, phường/xã, quận/huyện, tỉnh"}))
    ghi_chu = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: giao giờ hành chính"}))
    phuong_thuc_tt = forms.ChoiceField(choices=DonHang.PHUONG_THUC_TT, widget=forms.Select())
    so_luong = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={"min": "1", "max": "99"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_common_css()

    def clean_sdt(self):
        sdt = (self.cleaned_data.get("sdt") or "").strip()
        if not sdt.isdigit() or len(sdt) < 9:
            raise ValidationError("SĐT không hợp lệ (chỉ số, tối thiểu 9 chữ số).")
        return sdt


class AdminDonHangForm(forms.ModelForm):
    """Form cho Admin CRUD đơn hàng."""

    class Meta:
        model = DonHang
        fields = [
            "nguoi_dat",
            "san_pham",
            "ho_ten",
            "sdt",
            "dia_chi",
            "ghi_chu",
            "phuong_thuc_tt",
            "so_luong",
            "trang_thai",
        ]
        widgets = {
            "nguoi_dat": forms.Select(attrs={"class": "input"}),
            "san_pham": forms.Select(attrs={"class": "input"}),
            "ho_ten": forms.TextInput(attrs={"class": "input"}),
            "sdt": forms.TextInput(attrs={"class": "input"}),
            "dia_chi": forms.TextInput(attrs={"class": "input"}),
            "ghi_chu": forms.TextInput(attrs={"class": "input"}),
            "phuong_thuc_tt": forms.Select(attrs={"class": "input"}),
            "so_luong": forms.NumberInput(attrs={"class": "input", "min": "1", "max": "999"}),
            "trang_thai": forms.Select(attrs={"class": "input"}),
        }

    def clean_sdt(self):
        sdt = (self.cleaned_data.get("sdt") or "").strip()
        if not sdt.isdigit() or len(sdt) < 9:
            raise ValidationError("SĐT không hợp lệ (chỉ số, tối thiểu 9 chữ số).")
        return sdt

    def clean_so_luong(self):
        so_luong = self.cleaned_data.get("so_luong")
        if so_luong is None or int(so_luong) <= 0:
            raise ValidationError("Số lượng phải lớn hơn 0.")
        return so_luong

    def clean(self):
        cleaned_data = super().clean()
        instance = self.instance
        new_status = cleaned_data.get("trang_thai")

        # Validate nghiệp vụ chuyển trạng thái khi sửa đơn đã tồn tại.
        if instance and instance.pk and new_status and new_status != instance.trang_thai:
            if not can_transition(instance.trang_thai, new_status, actor_role="admin"):
                self.add_error(
                    "trang_thai",
                    ValidationError(
                        f"Không thể chuyển từ {instance.trang_thai} sang {new_status} theo luồng duyệt hiện tại."
                    ),
                )
        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        order.tong_tien = calculate_order_total(order.san_pham, order.so_luong)
        if commit:
            order.save()
        return order


class AdminUserForm(BaseStyledForm):
    """Form quản lý user với role User/Admin."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("admin", "Admin"),
    ]

    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True))
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial="user")
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, instance: User | None = None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        self._apply_common_css()
        self.fields["password"].help_text = "Bỏ trống nếu không đổi mật khẩu."

        if instance:
            self.initial.update(
                {
                    "username": instance.username,
                    "email": instance.email,
                    "role": "admin" if instance.is_staff else "user",
                    "is_active": instance.is_active,
                }
            )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Username đã tồn tại.")
        return username

    def clean_password(self):
        password = (self.cleaned_data.get("password") or "").strip()
        if not self.instance and not password:
            raise ValidationError("Vui lòng nhập password.")
        return password

    def save(self) -> User:
        if self.instance:
            user = self.instance
        else:
            user = User()

        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data.get("email", "")
        user.is_staff = self.cleaned_data["role"] == "admin"
        user.is_active = bool(self.cleaned_data.get("is_active"))

        password = self.cleaned_data.get("password", "")
        if password:
            user.set_password(password)
        elif not user.pk:
            raise ValidationError("Password là bắt buộc khi tạo mới.")

        user.save()
        return user
