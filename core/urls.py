# core/urls.py (final)
from django.urls import path, re_path
from . import views
from django.contrib.auth import views as auth_views # Pour les vues d'authentification par défaut
from .decorators import trial_required 




urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', trial_required(views.dashboard_view), name='dashboard'),
 # Authentification avec email confirmation
    path('register/', views.register_view, name='register'),
    # Un seul pattern pour l'activation, le token "itsdangerous" contient toutes les infos
    path('activate/<str:activation_token>/', views.activate_account, name='activate_account'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('resend-activation-email/', views.resend_activation_email, name='resend_activation_email'),
    path('company-settings/', views.company_settings_view, name='company_settings'),

    path('support/', views.support_page, name='support_page'),
    path('submit_support_request/', views.submit_support_request, name='submit_support_request'),
    path('contact-support/', views.contac_support, name='contact_support'),

    path('terms/', views.terms_and_conditions_page, name='terms_and_conditions'),
    path('privacy-policy/', views.privacy_policy_page, name='privacy_policy_page'),
    # Clients
    path('clients/', views.ClientListView.as_view(), name='client_list'),
    path('clients/new/', views.ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('clients/<int:pk>/edit/', views.ClientUpdateView.as_view(), name='client_update'),
    path('clients/<int:pk>/delete/', views.ClientDeleteView.as_view(), name='client_delete'),
    path('clients/search/', views.search_clients, name='search_clients'), # Recherche client

    # Products
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/new/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),

    # Invoices
    path('invoices/', trial_required(views.InvoiceListView.as_view()), name='invoice_list'),
    path('invoices/new/', trial_required(views.InvoiceCreateView.as_view()), name='invoice_create'),
    path('invoices/<int:pk>/', trial_required(views.InvoiceDetailView.as_view()), name='invoice_detail'),
    path('invoices/<int:pk>/edit/', trial_required(views.InvoiceUpdateView.as_view()), name='invoice_update'),
    path('invoices/<int:pk>/delete/', trial_required(views.InvoiceDeleteView.as_view()), name='invoice_delete'),
    # API pour récupérer les détails du produit (pour le formulaire de facture)
    path('api/products/<int:pk>/', views.get_product_details_api, name='api_product_details'),

    # Optionnel: Réinitialisation de mot de passe (utiliser les vues intégrées de Django)
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    path('invoices/<int:pk>/pdf/', views.generate_invoice_pdf, name='invoice_pdf'),
    path('invoices/<int:pk>/send-email/', views.send_invoice_email, name='invoice_send_email'),

    path('invoices/choose-template/', views.choose_invoice_template_view, name='choose_invoice_template'),
    path('dashboard/export/excel/', views.export_invoices_report, name='export_invoices_excel'),
    path('dashboard/export/csv/', views.export_invoices_report_csv, name='export_invoices_csv'),


    path('partner/join/', views.become_partner_view, name='become_partner'),
    path('partner/start-training/', views.start_training_view, name='start_training'),
    path('partner/training/', views.training_view, name='training'),

    path('partner/dashboard/', views.partner_dashboard_view, name='partner_dashboard'),
    path('partner/renew/', views.renew_contract_view, name='renew_partner_contract'),
    path('partner/withdrawal/', views.request_withdrawal_view, name='request_withdrawal'),
    path('partners/cancel/', views.cancel_partner_contract_view, name='cancel_partner_contract'),
]