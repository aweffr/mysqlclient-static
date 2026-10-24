from django.urls import path
from probe import views
urlpatterns = [path("health/", views.health), path("items/", views.items),
               path("items/<int:pk>/", views.items), path("async-cycle/", views.async_cycle)]
