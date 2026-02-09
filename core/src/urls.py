from django.urls import path

from .views import jsonrpc_endpoint

urlpatterns = [
    path("", jsonrpc_endpoint, name="jsonrpc-endpoint"),
]
