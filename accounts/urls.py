from django.urls import path

from .views import CurrentUserView, CustomAuthToken, LogoutView


app_name = "accounts"

urlpatterns = [
    path("login/", CustomAuthToken.as_view(), name="token-login"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
