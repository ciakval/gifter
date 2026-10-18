from django.urls import path
from . import views

urlpatterns = [
    path("add", views.CreateWishView.as_view(), name="add_wish")
]