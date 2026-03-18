from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dang-ky/", views.dang_ky, name="dang_ky"),
    path("dang-nhap/", views.dang_nhap, name="dang_nhap"),
    path("dang-xuat/", views.dang_xuat, name="dang_xuat"),

    path("dat-hang/<int:san_pham_id>/", views.dat_hang, name="dat_hang"),
    path("don-hang/", views.ds_don, name="ds_don"),
    path("vi-dien-tu/", views.wallet_view, name="wallet"),
    path("vi-dien-tu/nap-tien/", views.wallet_deposit, name="wallet_deposit"),
    path("don-hang/xac-nhan/<int:don_id>/", views.xac_nhan_don, name="xac_nhan_don"),
    path("don-hang/huy/<int:don_id>/", views.huy_don, name="huy_don"),

    # legacy URLs
    path("admin-don-hang/", views.ds_don_admin, name="ds_don_admin"),
    path("admin-don-hang/<int:don_id>/<str:hanh_dong>/", views.duyet_don, name="duyet_don"),

    # admin panel
    path("admin-panel/", views.admin_dashboard, name="admin_dashboard"),

    path("admin-panel/san-pham/", views.admin_sanpham_list, name="admin_sanpham_list"),
    path("admin-panel/san-pham/them/", views.admin_sanpham_create, name="admin_sanpham_create"),
    path("admin-panel/san-pham/<int:sp_id>/", views.admin_sanpham_detail, name="admin_sanpham_detail"),
    path("admin-panel/san-pham/<int:sp_id>/sua/", views.admin_sanpham_edit, name="admin_sanpham_edit"),
    path("admin-panel/san-pham/<int:sp_id>/xoa/", views.admin_sanpham_delete, name="admin_sanpham_delete"),

    path("admin-panel/don-hang/", views.admin_donhang_list, name="admin_donhang_list"),
    path("admin-panel/don-hang/them/", views.admin_donhang_create, name="admin_donhang_create"),
    path("admin-panel/don-hang/<int:don_id>/", views.admin_donhang_detail, name="admin_donhang_detail"),
    path("admin-panel/don-hang/<int:don_id>/sua/", views.admin_donhang_edit, name="admin_donhang_edit"),
    path("admin-panel/don-hang/<int:don_id>/xoa/", views.admin_donhang_delete, name="admin_donhang_delete"),
    path("admin-panel/don-hang/<int:don_id>/cap-nhat/", views.admin_donhang_update, name="admin_donhang_update"),

    path("admin-panel/users/", views.admin_user_list, name="admin_user_list"),
    path("admin-panel/users/them/", views.admin_user_create, name="admin_user_create"),
    path("admin-panel/users/<int:user_id>/sua/", views.admin_user_edit, name="admin_user_edit"),
    path("admin-panel/users/<int:user_id>/xoa/", views.admin_user_delete, name="admin_user_delete"),
]
