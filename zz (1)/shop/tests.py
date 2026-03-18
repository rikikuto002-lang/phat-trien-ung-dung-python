import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .forms import SanPhamForm
from .models import DonHang, SanPham, Wallet, WalletTransaction


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ShopFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="user1", password="123456")
        self.admin = User.objects.create_user(username="admin1", password="123456", is_staff=True)
        self.sp_active = SanPham.objects.create(ten="Nhan A", gia=100000, trang_thai="active")
        self.sp_inactive = SanPham.objects.create(ten="Nhan B", gia=200000, trang_thai="inactive")

    def test_guest_cannot_access_admin_panel(self):
        response = self.client.get(reverse("admin_dashboard"), follow=True)
        self.assertContains(response, "Vui lòng đăng nhập để tiếp tục")

    def test_search_filter_sort_products_in_admin_list(self):
        self.client.login(username="admin1", password="123456")
        SanPham.objects.create(ten="Nhan C", gia=50000, trang_thai="active")
        response = self.client.get(
            reverse("admin_sanpham_list"),
            {"q": "Nhan", "trang_thai": "active", "sort": "price_asc"},
        )
        ds = list(response.context["ds"])
        self.assertTrue(all(sp.trang_thai == "active" for sp in ds))
        self.assertEqual(ds[0].gia, 50000)

    def test_product_image_validation_rejects_bad_extension(self):
        bad_file = SimpleUploadedFile("bad.txt", b"abc", content_type="text/plain")
        form = SanPhamForm(data={"ten": "SP loi", "gia": 1000, "trang_thai": "active"}, files={"anh": bad_file})
        self.assertFalse(form.is_valid())
        self.assertIn("Chỉ cho phép ảnh", str(form.errors))

    def test_order_business_flow_user_and_admin(self):
        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "Giao nhanh",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
            },
            follow=True,
        )
        self.assertContains(response, "Đặt hàng thành công")
        don = DonHang.objects.get()
        self.assertEqual(don.tong_tien, 200000)
        self.assertEqual(don.trang_thai, "Pending")

        response = self.client.get(reverse("xac_nhan_don", args=[don.id]), follow=True)
        self.assertContains(response, "Đã cập nhật trạng thái đơn")
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, "Confirmed")

        self.client.logout()
        self.client.login(username="admin1", password="123456")
        response = self.client.post(
            reverse("admin_donhang_update", args=[don.id]),
            {"trang_thai": "Approved"},
            follow=True,
        )
        self.assertContains(response, "Đã cập nhật trạng thái đơn")
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, "Approved")

        self.client.logout()
        self.client.login(username="user1", password="123456")
        response = self.client.get(reverse("xac_nhan_don", args=[don.id]), follow=True)
        self.assertContains(response, "Không thể chuyển")
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, "Approved")

    def test_cannot_delete_product_that_has_orders(self):
        DonHang.objects.create(
            nguoi_dat=self.user,
            san_pham=self.sp_active,
            ho_ten="Nguyen Van A",
            sdt="0987654321",
            dia_chi="Thai Nguyen",
            ghi_chu="",
            phuong_thuc_tt="COD",
            so_luong=1,
            tong_tien=100000,
            trang_thai="Pending",
        )
        self.client.login(username="admin1", password="123456")
        response = self.client.post(reverse("admin_sanpham_delete", args=[self.sp_active.id]), follow=True)
        self.assertContains(response, "Không thể xoá sản phẩm đã phát sinh đơn hàng")
        self.assertTrue(SanPham.objects.filter(id=self.sp_active.id).exists())


    def test_wallet_payment_deducts_balance_and_creates_transaction(self):
        wallet = Wallet.objects.get(user=self.user)
        wallet.balance = 500000
        wallet.save()

        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "ViDienTu",
                "so_luong": 2,
            },
            follow=True,
        )

        self.assertContains(response, "Đặt hàng thành công")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 300000)
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet, transaction_type="payment").count(), 1)

    def test_wallet_order_refunds_when_cancelled(self):
        wallet = Wallet.objects.get(user=self.user)
        wallet.balance = 500000
        wallet.save()

        order = DonHang.objects.create(
            nguoi_dat=self.user,
            san_pham=self.sp_active,
            ho_ten="Nguyen Van A",
            sdt="0987654321",
            dia_chi="Thai Nguyen",
            ghi_chu="",
            phuong_thuc_tt="ViDienTu",
            so_luong=1,
            tong_tien=100000,
            trang_thai="Pending",
        )
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=100000,
            transaction_type="payment",
            order=order,
            note="Thanh toán đơn hàng",
        )
        wallet.balance = 400000
        wallet.save()

        self.client.login(username="user1", password="123456")
        response = self.client.get(reverse("huy_don", args=[order.id]), follow=True)
        self.assertContains(response, "Đã hoàn tiền vào ví điện tử")

        wallet.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(wallet.balance, 500000)
        self.assertTrue(order.da_hoan_tien)
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet, transaction_type="refund", order=order).count(), 1)
