from django.urls import path
from . import views
from .registration_views import SignUpView

urlpatterns = [
    # Início
    path('', views.home, name='home'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Categorias
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    
    # Transações
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('transactions/new/', views.TransactionCreateView.as_view(), name='transaction_create'),
    path('transactions/<int:pk>/', views.TransactionDetailView.as_view(), name='transaction_detail'),
    path('transactions/<int:pk>/edit/', views.TransactionUpdateView.as_view(), name='transaction_update'),
    path('transactions/<int:pk>/delete/', views.TransactionDeleteView.as_view(), name='transaction_delete'),
    
    # Relatórios
    path('reports/transactions/', views.report_transactions, name='report_transactions'),
    path('reports/transactions-by-category/', views.report_transactions_by_category, name='report_transactions_by_category'),
    path('reports/transactions-by-month/', views.report_transactions_by_month, name='report_transactions_by_month'),
    
    # Registro
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
]