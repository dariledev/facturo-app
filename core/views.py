# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import CompanyProfileForm, CustomUserCreationForm, CleanUserRegistrationForm
from .models import CompanyProfile 
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Client, Product, Invoice, InvoiceItem, CompanyProfile, InvoiceTemplate, Formation, Partenaire, MarketingMaterial, WithdrawalRequest
from .forms import ClientForm, ProductForm, InvoiceForm, InvoiceItemFormSet, CompanyProfileForm, InvoiceItemForm, SupportForm, WithdrawalRequestForm
from django.db import transaction 
from django.http import JsonResponse
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from django.http import HttpResponse
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.core.mail import EmailMessage
from django.db import transaction

from django.db.models import Sum, Count, F
from datetime import date, timedelta
from calendar import monthrange
from django.utils import timezone
from django.db.models.functions import ExtractMonth, ExtractYear
import pandas as pd
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime, date 
from django.db.models import Q 

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.core.mail import send_mail

from collections import OrderedDict 
from calendar import month_abbr 
import json 



from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site


from templated_mail.mail import BaseEmailMessage


from django.utils.html import strip_tags



from django import template
from decimal import Decimal





User = get_user_model()


@login_required
def dashboard_view(request):
    user = request.user
    user_invoices = Invoice.objects.filter(user=user)

    # --- NOUVELLE LOGIQUE POUR L'ESSAI GRATUIT ---
    days_left = None
    # Ajout de la condition 'and not user.is_paid_subscriber'
    if user.is_trial_active and user.trial_end_date and not user.is_paid_subscriber: 
        time_left = user.trial_end_date - timezone.now()
        if time_left.days >= 0:
            days_left = time_left.days
        else:
            days_left = 0 # L'essai a expiré mais n'a pas encore été désactivé
    # --- FIN DE LA NOUVELLE LOGIQUE ---

    # --- Logique de filtrage de période ---
    selected_period = request.GET.get('period', 'last_30_days')
    start_date_filter = request.GET.get('start_date')
    end_date_filter = request.GET.get('end_date')

    today = date.today()
    invoices_to_filter = user_invoices

    if selected_period == 'last_30_days':
        start_date_range = today - timedelta(days=29)
        end_date_range = today
        invoices_to_filter = invoices_to_filter.filter(issue_date__range=[start_date_range, end_date_range])
    elif selected_period == 'last_12_months':
        start_date_range = today - timedelta(days=365)
        end_date_range = today
        invoices_to_filter = invoices_to_filter.filter(issue_date__range=[start_date_range, end_date_range])
    elif selected_period == 'this_year':
        start_date_range = date(today.year, 1, 1)
        end_date_range = today # Jusqu'à aujourd'hui pour l'année en cours
        invoices_to_filter = invoices_to_filter.filter(issue_date__range=[start_date_range, end_date_range])
    elif selected_period == 'last_year':
        start_date_range = date(today.year - 1, 1, 1)
        end_date_range = date(today.year - 1, 12, 31)
        invoices_to_filter = invoices_to_filter.filter(issue_date__range=[start_date_range, end_date_range])
    elif selected_period == 'custom' and start_date_filter and end_date_filter:
        try:
            start_date_range = date.fromisoformat(start_date_filter)
            end_date_range = date.fromisoformat(end_date_filter)
            if start_date_range > end_date_range:
                messages.error(request, "La date de début ne peut pas être postérieure à la date de fin.")
                invoices_to_filter = invoices_to_filter.none()
            else:
                invoices_to_filter = invoices_to_filter.filter(issue_date__range=[start_date_range, end_date_range])
        except ValueError:
            messages.error(request, "Format de date invalide.")
            invoices_to_filter = invoices_to_filter.none()
    else: # Default if no period or custom is not fully specified
        start_date_range = today - timedelta(days=29)
        end_date_range = today
        invoices_to_filter = invoices_to_filter.filter(issue_date__range=[start_date_range, end_date_range])

    # --- Calcul des indicateurs clés (KPIs) - Mouvement de ces lignes ici ---
    total_invoices = invoices_to_filter.count()
    total_clients = Client.objects.filter(user=user).count()
    total_products = Product.objects.filter(user=user).count()
    
    total_revenue = invoices_to_filter.filter(status='Paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    pending_invoices_amount = invoices_to_filter.filter(status__in=['Sent', 'Partially Paid']).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    overdue_invoices_count = invoices_to_filter.filter(due_date__lt=today, status__in=['Sent', 'Partially Paid']).count()

    # --- Données pour les graphiques ---
    labels = []
    invoices_by_month_data = []
    revenue_by_month_data = []

    if selected_period == 'last_12_months':
        current_month = today.month
        current_year = today.year
        
        monthly_data_invoices = OrderedDict()
        monthly_data_revenue = OrderedDict()

        for i in range(12):
            month_obj = (date(current_year, current_month, 1) - timedelta(days=1)).replace(day=1) + timedelta(days=1)
            labels.insert(0, month_obj.strftime('%b %Y'))
            monthly_data_invoices[month_obj.strftime('%b %Y')] = 0
            monthly_data_revenue[month_obj.strftime('%b %Y')] = 0
            
            current_month -= 1
            if current_month == 0:
                current_month = 12
                current_year -= 1

        invoices_counts = invoices_to_filter.annotate(month=ExtractMonth('issue_date'), year=ExtractYear('issue_date')) \
                                             .values('year', 'month') \
                                             .annotate(count=Count('id')) \
                                             .order_by('year', 'month')

        revenues = invoices_to_filter.filter(status='Paid').annotate(month=ExtractMonth('issue_date'), year=ExtractYear('issue_date')) \
                                      .values('year', 'month') \
                                      .annotate(total_revenue=Sum('total_amount')) \
                                      .order_by('year', 'month')
        
        for entry in invoices_counts:
            month_label = date(entry['year'], entry['month'], 1).strftime('%b %Y')
            if month_label in monthly_data_invoices:
                monthly_data_invoices[month_label] = entry['count']

        for entry in revenues:
            month_label = date(entry['year'], entry['month'], 1).strftime('%b %Y')
            if month_label in monthly_data_revenue:
                monthly_data_revenue[month_label] = float(entry['total_revenue'])

        invoices_by_month_data = list(monthly_data_invoices.values())
        revenue_by_month_data = list(monthly_data_revenue.values())

    else:
        if selected_period == 'this_year':
            year = today.year
            start_month = 1
            end_month = today.month
        elif selected_period == 'last_year':
            year = today.year - 1
            start_month = 1
            end_month = 12
        else:
            year = start_date_range.year
            start_month = start_date_range.month
            end_month = end_date_range.month
            if start_date_range.year != end_date_range.year:
                labels = []
                current_date = start_date_range
                while current_date <= end_date_range:
                    labels.append(current_date.strftime('%b %Y'))
                    if current_date.month == 12:
                        current_date = date(current_date.year + 1, 1, 1)
                    else:
                        current_date = date(current_date.year, current_date.month + 1, 1)

                monthly_data_invoices = OrderedDict((label, 0) for label in labels)
                monthly_data_revenue = OrderedDict((label, 0) for label in labels)

                invoices_counts = invoices_to_filter.annotate(month=ExtractMonth('issue_date'), year=ExtractYear('issue_date')) \
                                                     .values('year', 'month') \
                                                     .annotate(count=Count('id')) \
                                                     .order_by('year', 'month')
                revenues = invoices_to_filter.filter(status='Paid').annotate(month=ExtractMonth('issue_date'), year=ExtractYear('issue_date')) \
                                              .values('year', 'month') \
                                              .annotate(total_revenue=Sum('total_amount')) \
                                              .order_by('year', 'month')

                for entry in invoices_counts:
                    month_label = date(entry['year'], entry['month'], 1).strftime('%b %Y')
                    if month_label in monthly_data_invoices:
                        monthly_data_invoices[month_label] = entry['count']

                for entry in revenues:
                    month_label = date(entry['year'], entry['month'], 1).strftime('%b %Y')
                    if month_label in monthly_data_revenue:
                        monthly_data_revenue[month_label] = float(entry['total_revenue'])

                invoices_by_month_data = list(monthly_data_invoices.values())
                revenue_by_month_data = list(monthly_data_revenue.values())
                
            else:
                labels = [month_abbr[m] for m in range(1, 13)]
                
                monthly_data_invoices = OrderedDict()
                monthly_data_revenue = OrderedDict()
                for i in range(1, 13):
                    monthly_data_invoices[month_abbr[i]] = 0
                    monthly_data_revenue[month_abbr[i]] = 0

                invoices_counts = invoices_to_filter.filter(issue_date__year=year).annotate(month=ExtractMonth('issue_date')) \
                                                     .values('month') \
                                                     .annotate(count=Count('id')) \
                                                     .order_by('month')
                revenues = invoices_to_filter.filter(status='Paid', issue_date__year=year).annotate(month=ExtractMonth('issue_date')) \
                                              .values('month') \
                                              .annotate(total_revenue=Sum('total_amount')) \
                                              .order_by('month')
                
                for entry in invoices_counts:
                    month_name = month_abbr[entry['month']]
                    monthly_data_invoices[month_name] = entry['count']

                for entry in revenues:
                    month_name = month_abbr[entry['month']]
                    monthly_data_revenue[month_name] = float(entry['total_revenue'])
                
                invoices_by_month_data = list(monthly_data_invoices.values())
                revenue_by_month_data = list(monthly_data_revenue.values())

    # --- Activité Récente ---
    recent_invoices = user_invoices.order_by('-issue_date')[:5]
    recent_clients = Client.objects.filter(user=user).order_by('-created_at')[:5]

    # --- LOGIQUE D'AFFICHAGE DU BOUTON PARTENAIRE ---
    is_validated_partner = False
    try:
        if hasattr(request.user, 'partenaire'):
            if request.user.partenaire.status == 'validated':
                is_validated_partner = True
    except Partenaire.DoesNotExist:
        pass

    context = {
        'selected_period': selected_period,
        'start_date_filter': start_date_filter,
        'end_date_filter': end_date_filter,
        'total_invoices': total_invoices,
        'total_clients': total_clients,
        'total_products': total_products,
        'total_revenue': total_revenue,
        'pending_invoices_amount': pending_invoices_amount,
        'overdue_invoices_count': overdue_invoices_count,
        'labels': json.dumps(labels),
        'invoices_by_month_data': json.dumps(invoices_by_month_data),
        'revenue_by_month_data': json.dumps(revenue_by_month_data),
        'recent_invoices': recent_invoices,
        'recent_clients': recent_clients,
        'days_left': days_left,
        'is_validated_partner': is_validated_partner,
    }
    return render(request, 'dashboard.html', context)



@login_required
def partner_dashboard_view(request):
    """
    Vue du tableau de bord partenaire avec toutes les fonctionnalités intégrées.
    """
    try:
        partenaire = Partenaire.objects.get(user=request.user)
    except Partenaire.DoesNotExist:
        messages.error(request, "Vous n'êtes pas un partenaire valide.")
        return redirect('dashboard')
        
    if partenaire.status != 'validated':
        messages.warning(request, "Votre compte partenaire n'est pas encore validé.")
        return redirect('dashboard')

    # Logique pour la soumission du formulaire de support
    if request.method == 'POST':
        support_form = SupportForm(request.POST)
        if support_form.is_valid():
            subject = support_form.cleaned_data['subject']
            message = support_form.cleaned_data['message']
            
            try:
                send_mail(
                    f"[Facturo Partner Support] {subject}",
                    f"Message de {request.user.email} (Partenaire) :\n\n{message}",
                    'facturo@tak-media.tech',
                    ['facturo@tak-media.tech'],
                    fail_silently=False,
                )
                messages.success(request, "Votre message a été envoyé avec succès.")
            except Exception as e:
                messages.error(request, f"Une erreur s'est produite lors de l'envoi : {e}")
            
            return redirect('partner_dashboard')
    else:
        support_form = SupportForm()

    # Calcul des performances du partenaire
    referral_link = request.build_absolute_uri(f"/register/?ref={partenaire.referral_code}")
    total_clients_referred = partenaire.user.filleuls.count()
    
    # Les clients convertis sont ceux qui ont un abonnement payant
    converted_clients = partenaire.user.filleuls.filter(is_paid_subscriber=True)
    converted_clients_count = converted_clients.count()
    
    # Le calcul des revenus est toujours utile pour les statistiques globales
    revenue_per_client = Decimal('6500')
    total_revenue_generated = converted_clients_count * revenue_per_client
    
    # Le solde à afficher est maintenant directement lié au champ `balance` du partenaire
    commission_earned = partenaire.balance 
    
    # Mettez à jour la vérification d'éligibilité pour utiliser le nouveau champ
    MIN_WITHDRAWAL_AMOUNT = Decimal('1500')
    is_eligible_for_withdrawal = commission_earned >= MIN_WITHDRAWAL_AMOUNT
    
    latest_referrals = partenaire.user.filleuls.all().order_by('-date_joined')[:5]
    marketing_materials = MarketingMaterial.objects.all().order_by('-uploaded_at')
    today = timezone.now().date()
    
    context = {
        'partenaire': partenaire,
        'referral_link': referral_link,
        'page_title': "Tableau de bord partenaire",
        'marketing_materials': marketing_materials,
        'total_clients_referred': total_clients_referred,
        'converted_clients_count': converted_clients_count,
        'total_revenue_generated': total_revenue_generated,
        'commission_earned': commission_earned,
        'latest_referrals': latest_referrals,
        'today': today,
        'support_form': support_form,
        'MIN_WITHDRAWAL_AMOUNT': MIN_WITHDRAWAL_AMOUNT,
        'is_eligible_for_withdrawal': is_eligible_for_withdrawal,
        'withdrawal_form': WithdrawalRequestForm(),
    }
    return render(request, 'partners/partner_dashboard.html', context)





def home(request):
    return render(request, 'core/home.html')



def register_view(request):
    if request.method == 'POST':
        form = CleanUserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
             # --- Capture du parrainage ---
            referral_code = request.GET.get('ref')
            if referral_code:
                try:
                    partenaire_parrain = Partenaire.objects.get(referral_code=referral_code)
                    # CORRECTION : Utiliser le champ "referred_by"
                    user.referred_by = partenaire_parrain.user
                except Partenaire.DoesNotExist:
                    # Gérer le cas où le code de parrainage est invalide
                    pass
            # --- Fin de la capture ---
            user.is_active = False # L'utilisateur est inactif jusqu'à la confirmation de l'e-mail

            # --- NOUVEAU CODE POUR LA PÉRIODE D'ESSAI ---
            user.is_trial_active = True
            user.trial_start_date = timezone.now()
            # ---------------------------------------------

            user.save()

            # Envoyer l'email de confirmation
            send_confirmation_email(request, user)

            messages.success(request, "Votre compte a été créé. Veuillez vérifier votre adresse e-mail pour activer votre compte.")
            return redirect('login')
        else:
            messages.error(request, "Erreur lors de la création du compte. Veuillez corriger les erreurs.")
    else:
        form = CleanUserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


def send_confirmation_email(request, user):
    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    token = serializer.dumps({'user_id': user.pk, 'email': user.email})
    current_site = get_current_site(request)
    mail_subject = 'Activez votre compte Facturo'
    message = render_to_string('emails/account_activation_email.html', {
        'user': user,
        'domain': current_site.domain,
        'uid': user.pk, # Ou encodez l'ID utilisateur comme vous le souhaitez
        'token': token,
        'protocol': 'https' if request.is_secure() else 'http',
    })
    email = EmailMessage(
        mail_subject, message, to=[user.email]
    )
    try:
        email.send()
        messages.info(request, "Un e-mail de confirmation a été envoyé à votre adresse. Veuillez le vérifier pour activer votre compte.")
    except Exception as e:
        messages.error(request, f"Impossible d'envoyer l'e-mail de confirmation. Veuillez contacter le support. Erreur: {e}")



        
def activate_account(request, activation_token): # Renommez 'token' en 'activation_token' ici
    try:
        serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
        data = serializer.loads(activation_token, max_age=60*60*24) # Utilisez activation_token ici
        user = User.objects.get(pk=data['user_id'], email=data['email'])
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, SignatureExpired, BadTimeSignature):
        user = None

    if user is not None and not user.email_confirmed:
        user.is_active = True
        user.email_confirmed = True
        user.save()
        messages.success(request, "Votre compte a été activé avec succès ! Vous pouvez maintenant vous connecter.")
        return redirect('login')
    else:
        messages.error(request, "Le lien d'activation est invalide ou a expiré, ou votre compte est déjà activé.")
        return redirect('home') # Ou une page d'erreur spécifique

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password) # Utilisez request dans authenticate
            if user is not None:
                if user.is_active and user.email_confirmed: # Vérifiez si le compte est actif et l'email confirmé
                    login(request, user)
                    messages.success(request, f"Bienvenue, {username} !")
                    return redirect('home')
                elif not user.email_confirmed:
                    messages.warning(request, "Votre compte n'a pas encore été activé. Veuillez vérifier votre e-mail.")
                    # Optionnel: Proposer de renvoyer l'email de confirmation
                    return render(request, 'registration/resend_confirmation.html', {'user_email': user.email})
                else: # if not user.is_active (pas email_confirmed)
                    messages.error(request, "Votre compte est inactif. Veuillez contacter l'administrateur.")
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect('home')







@login_required
def company_settings_view(request):
    try:
        company_profile = CompanyProfile.objects.get(user=request.user)
    except CompanyProfile.DoesNotExist:
        company_profile = CompanyProfile(user=request.user)

    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, request.FILES, instance=company_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil d'entreprise mis à jour avec succès !")
            return redirect('company_settings')
        else:
            messages.error(request, "Erreur lors de la mise à jour du profil d'entreprise.")
    else:
        form = CompanyProfileForm(instance=company_profile)
    return render(request, 'company_settings.html', {'form': form})




# --- Mixins personnalisés ---
class OwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin pour s'assurer que l'utilisateur est connecté et est le propriétaire de l'objet.
    """
    def test_func(self):
        obj = self.get_object()
        return obj.user == self.request.user

# --- Vues pour Client ---
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'clients/client_list.html'
    context_object_name = 'clients'
    paginate_by = 10

    def get_queryset(self):
        return Client.objects.filter(user=self.request.user)

class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'clients/client_form.html'
    success_url = reverse_lazy('client_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Client créé avec succès !")
        return super().form_valid(form)

class ClientUpdateView(OwnerRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'clients/client_form.html'
    context_object_name = 'client'

    def get_success_url(self):
        messages.success(self.request, "Client mis à jour avec succès !")
        return reverse_lazy('client_list')

class ClientDeleteView(OwnerRequiredMixin, DeleteView):
    model = Client
    template_name = 'clients/client_confirm_delete.html'
    context_object_name = 'client'
    success_url = reverse_lazy('client_list')

    def form_valid(self, form):
        messages.success(self.request, "Client supprimé avec succès !")
        return super().form_valid(form)

class ClientDetailView(OwnerRequiredMixin, DetailView):
    model = Client
    template_name = 'clients/client_detail.html'
    context_object_name = 'client'

# --- Vues pour Product ---
class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 10

    def get_queryset(self):
        # Start with products belonging to the current user
        queryset = Product.objects.filter(user=self.request.user)

        # Get the search query from the URL (e.g., ?q=searchTerm)
        query = self.request.GET.get('q')

        # If a query exists, filter the queryset
        if query:
            # Use Q objects for OR queries on multiple fields
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=query) | # Case-insensitive search by name
                Q(description__icontains=query) # Case-insensitive search by description
            )

        return queryset.order_by('name') # Order by name for consistency


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('product_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Produit créé avec succès !")
        return super().form_valid(form)

class ProductUpdateView(OwnerRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    context_object_name = 'product'

    def get_success_url(self):
        messages.success(self.request, "Produit mis à jour avec succès !")
        return reverse_lazy('product_list')

class ProductDeleteView(OwnerRequiredMixin, DeleteView):
    model = Product
    template_name = 'products/product_confirm_delete.html'
    context_object_name = 'product'
    success_url = reverse_lazy('product_list')

    def form_valid(self, form):
        messages.success(self.request, "Produit supprimé avec succès !")
        return super().form_valid(form)





# --- Vues pour Invoice ---

class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'invoices/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 10

    def get_queryset(self):
        queryset = Invoice.objects.filter(user=self.request.user).select_related('client').order_by('-issue_date')

        # --- Logique de recherche ajoutée ici ---
        query = self.request.GET.get('q') # Récupère le terme de recherche depuis l'URL (?q=...)

        if query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=query) | # Recherche par numéro de facture
                Q(client__name__icontains=query) |   # Recherche par nom du client
                Q(total_amount__icontains=query)     # Recherche par montant total (si l'utilisateur tape un montant)
            ).distinct() # Utiliser .distinct() pour éviter les doublons si une facture correspond à plusieurs critères
        # --- Fin de la logique de recherche ---

        return queryset

    # Optionnel: pour conserver le terme de recherche dans la pagination
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '') # Passer le terme de recherche au template
        return context


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True
)



class InvoiceCreateView(LoginRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'invoices/invoice_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if 'form' in kwargs: 
            current_invoice_instance = kwargs['form'].instance
        else:
            current_invoice_instance = self.object

        if self.request.POST:
            items_formset = InvoiceItemFormSet(self.request.POST, 
                                               instance=current_invoice_instance,
                                               prefix='item', 
                                               form_kwargs={'user': self.request.user})
            data['items'] = items_formset
        else:
            data['items'] = InvoiceItemFormSet(instance=None, prefix='item', form_kwargs={'user': self.request.user})
        return data

    def get_initial(self):
        """
        Pré-remplit le champ 'template' du formulaire si un 'template_id'
        est présent dans l'URL.
        """
        initial = super().get_initial()
        template_id = self.request.GET.get('template_id')
        if template_id:
            try:
                # Récupère l'instance du modèle de facture choisi
                initial['template'] = InvoiceTemplate.objects.get(id=template_id)
            except InvoiceTemplate.DoesNotExist:
                # Gère le cas où l'ID du template est invalide
                messages.error(self.request, "Le modèle de facture sélectionné n'existe pas.")
        return initial

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.user = self.request.user

        items_formset = InvoiceItemFormSet(self.request.POST, 
                                           instance=self.object, 
                                           prefix='item', 
                                           form_kwargs={'user': self.request.user})

        with transaction.atomic():
            if items_formset.is_valid():
                self.object.save()
                items_formset.save()
                self.object.calculate_totals()
                messages.success(self.request, "Facture créée avec succès !")
                return redirect(self.object.get_absolute_url())
            else:
                messages.error(self.request, "Erreur lors de la création de la facture. Veuillez vérifier les articles.")
                return self.render_to_response(self.get_context_data(form=form, items=items_formset))

    def get_success_url(self):
        return reverse_lazy('invoice_detail', kwargs={'pk': self.object.pk})



class InvoiceUpdateView(OwnerRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'invoices/invoice_form.html'
    context_object_name = 'invoice'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = InvoiceItemFormSet(self.request.POST, instance=self.object, prefix='item', form_kwargs={'user': self.request.user})
        else:
            data['items'] = InvoiceItemFormSet(instance=self.object, prefix='item', form_kwargs={'user': self.request.user})
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items']

        with transaction.atomic():
            self.object = form.save() # Sauvegarde la facture parente
            
            # Re-associer l'instance de la facture au formset
            items_formset.instance = self.object

            if items_formset.is_valid():
                items_formset.save()
                self.object.calculate_totals()
                messages.success(self.request, "Facture mise à jour avec succès !")
                return redirect(self.object.get_absolute_url())
            else:
                messages.error(self.request, "Erreur lors de la mise à jour de la facture. Veuillez vérifier les articles.")
                return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('invoice_detail', kwargs={'pk': self.object.pk})





class InvoiceDeleteView(OwnerRequiredMixin, DeleteView):
    model = Invoice
    template_name = 'invoices/invoice_confirm_delete.html'
    context_object_name = 'invoice'
    success_url = reverse_lazy('invoice_list')

    def form_valid(self, form):
        messages.success(self.request, "Facture supprimée avec succès !")
        return super().form_valid(form)

class InvoiceDetailView(OwnerRequiredMixin, DetailView):
    model = Invoice
    template_name = 'invoices/invoice_detail.html'
    context_object_name = 'invoice'

def search_clients(request):
    query = request.GET.get('q')
    
    # Commencez par tous les clients de l'utilisateur
    clients_list = Client.objects.filter(user=request.user).order_by('name') # Ajoute un ordre par défaut

    if query:
        # Si une requête est présente, filtrez la liste
        clients_list = clients_list.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(address__icontains=query) |
            Q(phone__icontains=query)
        ).distinct()
    
    # Initialise le Paginator avec la liste filtrée ou complète des clients
    paginator = Paginator(clients_list, 10)  # 10 clients par page
    page = request.GET.get('page')

    try:
        # Tente de récupérer la page demandée
        clients = paginator.page(page)
    except PageNotAnInteger:
        # Si 'page' n'est pas un entier, afficher la première page
        clients = paginator.page(1)
    except EmptyPage:
        # Si la page est hors de portée (par exemple, 99999), affichez la dernière page
        clients = paginator.page(paginator.num_pages)

    # Passe la variable paginée 'clients' (qui est en fait un objet Page)
    # au template sous le nom 'page_obj' comme attendu par le template.
    return render(request, 'clients/client_list.html', {'page_obj': clients, 'query': query})


def get_product_details_api(request, pk):
    try:
        product = Product.objects.get(pk=pk, user=request.user)
        data = {
            'name': product.name,
            'description': product.description,
            'unit_price': str(product.unit_price), # Convertir en chaîne pour JSON
            'tax_rate': str(product.tax_rate),
            'sku': product.sku,
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Produit non trouvé'}, status=404)


@login_required
def choose_invoice_template_view(request):
    templates = InvoiceTemplate.objects.all()
    context = {
        'templates': templates
    }
    return render(request, 'invoices/choose_template.html', context)


@login_required
def generate_invoice_pdf(request, pk):
    try:
        invoice = Invoice.objects.get(pk=pk, user=request.user)
    except Invoice.DoesNotExist:
        messages.error(request, "Facture introuvable.")
        return redirect('invoice_list')

    # Calculez le montant de la remise ici
    discount_amount = Decimal('0.00')
    if invoice.discount:
        discount_amount = (invoice.subtotal * (invoice.discount / 100)).quantize(Decimal('0.01'))

    template_path = 'invoices/invoice_classic.html'
    if invoice.template:
        template_path = invoice.template.template_file
    
    html_string = render_to_string(template_path, {
        'invoice': invoice,
        'company': invoice.company_profile,
        'client': invoice.client,
        'invoice_items': invoice.items.all(),
        'discount_amount': discount_amount, # Passez le montant de la remise au contexte
    })
    
    html = HTML(string=html_string, base_url=request.build_absolute_uri())

    css_string = render_to_string('invoices/invoice_pdf_style.css')
    css = CSS(string=css_string)

    pdf_file = html.write_pdf(stylesheets=[css])

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="facture_{invoice.invoice_number}.pdf"'
    return response


@login_required
def send_invoice_email(request, pk):
    try:
        invoice = Invoice.objects.get(pk=pk, user=request.user)
    except Invoice.DoesNotExist:
        messages.error(request, "Facture introuvable.")
        return redirect('invoice_list')

    if request.method == 'POST':
        # Données du formulaire d'envoi (si vous en avez un)
        # Pour l'instant, on prend l'email du client par défaut et un message simple
        recipient_email = request.POST.get('recipient_email', invoice.client.email)
        subject_template = f"Votre facture {invoice.invoice_number} de {invoice.company_profile.name}"
        message_body_template = render_to_string('emails/invoice_email_body.html', {
            'invoice': invoice,
            'client_name': invoice.client.name,
            'company_name': invoice.company_profile.name,
            'user': request.user,
        })
        custom_message = request.POST.get('custom_message', '') # Optionnel: message personnalisé

        if custom_message:
            message_body_template = f"{custom_message}\n\n{message_body_template}"


        # Générer le PDF en tant que pièce jointe
        context_pdf = {
            'invoice': invoice,
            'company': invoice.company_profile,
            'client': invoice.client,
        }
        html_string_pdf = render_to_string('invoices/invoice_pdf_template.html', context_pdf)
        html_pdf = HTML(string=html_string_pdf, base_url=request.build_absolute_uri())
        css_string_pdf = render_to_string('invoices/invoice_pdf_style.css')
        css_pdf = CSS(string=css_string_pdf)
        pdf_file = html_pdf.write_pdf(stylesheets=[css_pdf])

        # Créer l'email
        email = EmailMessage(
            subject=subject_template,
            body=message_body_template,
            from_email=request.user.email, # L'expéditeur sera l'email de l'utilisateur ou le DEFAULT_FROM_EMAIL
            to=[recipient_email],
        )
        email.attach(f'Facture_{invoice.invoice_number}.pdf', pdf_file, 'application/pdf')

        try:
            email.send()
            messages.success(request, f"Facture {invoice.invoice_number} envoyée avec succès à {recipient_email} !")
            # Mettre à jour le statut de la facture si elle était en brouillon
            if invoice.status == 'Draft':
                invoice.status = 'Sent'
                invoice.save()
        except Exception as e:
            messages.error(request, f"Erreur lors de l'envoi de la facture : {e}")

        return redirect('invoice_detail', pk=invoice.pk)
    
    # Pour la méthode GET, affichez un formulaire ou une page de confirmation
    return render(request, 'invoices/invoice_send_email.html', {'invoice': invoice, 'default_email': invoice.client.email})



@login_required
def export_invoices_report(request):
    user_invoices = Invoice.objects.filter(user=request.user)

    # Récupérer les mêmes paramètres de filtrage que le tableau de bord
    period = request.GET.get('period', 'last_12_months')
    start_date_filter = request.GET.get('start_date')
    end_date_filter = request.GET.get('end_date')

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=365) # Valeur par défaut

    if period == 'last_30_days':
        start_date = end_date - timedelta(days=30)
    elif period == 'this_year':
        start_date = date(end_date.year, 1, 1)
        end_date = date(end_date.year, 12, 31)
    elif period == 'last_year':
        start_date = date(end_date.year - 1, 1, 1)
        end_date = date(end_date.year - 1, 12, 31)
    elif period == 'custom' and start_date_filter and end_date_filter:
        try:
            start_date = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Format de date invalide pour l'export. Veuillez utiliser AAAA-MM-JJ.")
            # Revert to default or handle error appropriately
            start_date = end_date - timedelta(days=365)
            end_date = timezone.now().date()

    # Filtrer les factures dans la période sélectionnée
    filtered_invoices = user_invoices.filter(
        issue_date__gte=start_date,
        issue_date__lte=end_date
    ).select_related('client', 'company_profile') # Optimisation des requêtes

    # Préparer les données pour pandas
    data = []
    for invoice in filtered_invoices:
        data.append({
            'Numero Facture': invoice.invoice_number,
            'Client': invoice.client.name,
            'Date Emission': invoice.issue_date,
            'Date Echeance': invoice.due_date,
            'Statut': invoice.get_status_display(),
            'Sous-Total (FCFA)': float(invoice.subtotal),
            'Montant TVA (FCFA)': float(invoice.tax_amount),
            'Remise (%)': float(invoice.discount),
            'Frais Port (FCFA)': float(invoice.shipping_cost),
            'Total TTC (FCFA)': float(invoice.total_amount),
            'Emetteur': invoice.company_profile.name if invoice.company_profile else 'N/A',
            'Notes': invoice.notes,
        })

    df = pd.DataFrame(data)

    # Préparer la réponse HTTP pour le fichier Excel
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, sheet_name='Factures', index=False)
    writer.close() # Utilisez writer.close() pour les versions récentes de pandas
    output.seek(0) # Remettre le curseur au début du fichier

    filename = f"rapport_factures_{start_date}_{end_date}.xlsx"
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# Vue pour l'exportation CSV (similaire, mais utilisant to_csv)
@login_required
def export_invoices_report_csv(request):
    user_invoices = Invoice.objects.filter(user=request.user)

    # Récupérer les mêmes paramètres de filtrage que le tableau de bord
    period = request.GET.get('period', 'last_12_months')
    start_date_filter = request.GET.get('start_date')
    end_date_filter = request.GET.get('end_date')

    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=365) # Valeur par défaut

    if period == 'last_30_days':
        start_date = end_date - timedelta(days=30)
    elif period == 'this_year':
        start_date = date(end_date.year, 1, 1)
        end_date = date(end_date.year, 12, 31)
    elif period == 'last_year':
        start_date = date(end_date.year - 1, 1, 1)
        end_date = date(end_date.year - 1, 12, 31)
    elif period == 'custom' and start_date_filter and end_date_filter:
        try:
            start_date = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Format de date invalide pour l'export. Veuillez utiliser AAAA-MM-JJ.")
            start_date = end_date - timedelta(days=365)
            end_date = timezone.now().date()

    filtered_invoices = user_invoices.filter(
        issue_date__gte=start_date,
        issue_date__lte=end_date
    ).select_related('client', 'company_profile')

    data = []
    for invoice in filtered_invoices:
        data.append({
            'Numero Facture': invoice.invoice_number,
            'Client': invoice.client.name,
            'Date Emission': invoice.issue_date,
            'Date Echeance': invoice.due_date,
            'Statut': invoice.get_status_display(),
            'Sous-Total (FCFA)': float(invoice.subtotal),
            'Montant TVA (FCFA)': float(invoice.tax_amount),
            'Remise (%)': float(invoice.discount),
            'Frais Port (FCFA)': float(invoice.shipping_cost),
            'Total TTC (FCFA)': float(invoice.total_amount),
            'Emetteur': invoice.company_profile.name if invoice.company_profile else 'N/A',
            'Notes': invoice.notes,
        })

    df = pd.DataFrame(data)

    response = HttpResponse(content_type='text/csv')
    filename = f"rapport_factures_{start_date}_{end_date}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    df.to_csv(response, index=False, encoding='utf-8-sig') # Utilisez utf-8-sig pour les caractères spéciaux

    return response






def resend_activation_email(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email, email_confirmed=False)
            send_confirmation_email(request, user)
            messages.success(request, "Un nouvel e-mail de confirmation a été envoyé. Vérifiez votre boîte de réception.")
        except User.DoesNotExist:
            messages.error(request, "Aucun compte inactif trouvé pour cette adresse e-mail.")
        return redirect('login')
    return redirect('home') # Ou une page d'erreur






def support_page(request):
    """
    Vue pour afficher la page de support.
    """
    return render(request, 'core/support.html')



def contac_support(request):
    """
    Vue pour afficher la page de support.
    """
    return render(request, 'core/contact_support.html')




def submit_support_request(request):
    """
    Vue pour gérer la soumission du formulaire de support.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject_type = request.POST.get('subject')
        description = request.POST.get('description')
        attachment = request.FILES.get('attachment') # Pour gérer le fichier joint

        # Construction du sujet de l'email pour vous
        email_subject_for_us = f"Demande de Support Facturo : [{subject_type}] - {name}"
        
        # Contexte pour le template d'email (optionnel mais recommandé pour des emails plus propres)
        context = {
            'name': name,
            'email': email,
            'subject_type': subject_type,
            'description': description,
        }
        
        # Render le contenu HTML de l'email
        html_message = render_to_string('emails/support_request_email.html', context)
        plain_message = strip_tags(html_message) # Créer une version texte brut

        try:
            email_to_send = EmailMessage(
                email_subject_for_us,
                html_message,
                settings.DEFAULT_FROM_EMAIL, # L'adresse email de l'expéditeur (vous)
                ['facturo@tak-media.tech'], # L'adresse email de votre support
                reply_to=[email] # Pour que vous puissiez répondre directement à l'utilisateur
            )
            email_to_send.content_subtype = "html" # S'assurer que le type de contenu est HTML

            if attachment:
                email_to_send.attach(attachment.name, attachment.read(), attachment.content_type)
            
            email_to_send.send()
            
            messages.success(request, "Votre demande de support a été envoyée avec succès ! Nous vous répondrons dans les 24 heures ouvrables.")
            return redirect('support_page') # Redirige vers la page de support ou une page de confirmation
        except Exception as e:
            messages.error(request, f"Une erreur est survenue lors de l'envoi de votre demande. Veuillez réessayer. Erreur: {e}")
            return redirect('support_page') # Rester sur la page de support en cas d'erreur
    return redirect('support_page') # Si la méthode n'est pas POST, rediriger






register = template.Library()

@register.filter
def multiply(value, arg):
    """
    Multiplie la valeur par l'argument.
    Utilisation: {{ value|multiply:arg }}
    Gère les types Decimal pour les calculs monétaires.
    """
    try:
        return Decimal(value) * Decimal(arg)
    except (ValueError, TypeError):
        try:
            return float(value) * float(arg)
        except (ValueError, TypeError):
            return '' # Retourne une chaîne vide en cas d'erreur de conversion

@register.filter
def divide(value, arg):
    """
    Divise la valeur par l'argument.
    Utilisation: {{ value|divide:arg }}
    Gère les types Decimal pour les calculs monétaires.
    """
    try:
        arg_decimal = Decimal(arg)
        if arg_decimal == 0:
            return 0 # Évite la division par zéro
        return Decimal(value) / arg_decimal
    except (ValueError, TypeError):
        try:
            arg_float = float(arg)
            if arg_float == 0:
                return 0
            return float(value) / arg_float
        except (ValueError, TypeError):
            return '' # Retourne une chaîne vide en cas d'erreur de conversion



def terms_and_conditions_page(request):
    """
    Vue pour afficher la page des Conditions Générales d'Utilisation.
    """
    return render(request, 'core/terms.html')


def privacy_policy_page(request):
    """
    
    """
    return render(request, 'core/privacy_policy.html')




@login_required
def become_partner_view(request):
    # Vue de présentation du programme
    context = {
        'page_title': "Devenez Partenaire",
        'description': "Rejoignez l'équipe de vente Facturo et gagnez des revenus passifs en aidant les entreprises à optimiser leur gestion de facturation.",
        'benefits': [
            "Gagnez jusqu'à 30% de commission sur chaque abonnement.",
            "Formation complète et gratuite sur l'outil et les techniques de vente.",
            "Accès à un tableau de bord partenaire pour suivre vos gains.",
            "Flexibilité et autonomie."
        ],
        'call_to_action': "Prêt à démarrer ? Cliquez pour commencer la formation !"
    }
    return render(request, 'partners/become_partner.html', context)


@login_required
def start_training_view(request):
    if request.method == 'POST':
        # Assurez-vous que la formation de base existe dans l'administration
        try:
            formation = Formation.objects.get(title="Programme de Vente Facturo")
        except Formation.DoesNotExist:
            messages.error(request, "La formation n'est pas encore disponible. Veuillez réessayer plus tard.")
            return redirect('become_partner')

        if not Partenaire.objects.filter(user=request.user).exists():
            Partenaire.objects.create(user=request.user, formation=formation)
            messages.success(request, "Formation démarrée avec succès ! Bonne chance !")
        else:
            messages.info(request, "Vous êtes déjà inscrit à la formation.")
        
        return redirect('training')

    return redirect('become_partner')


@login_required
def training_view(request):
    try:
        partenaire = Partenaire.objects.get(user=request.user)
        formation = partenaire.formation
    except Partenaire.DoesNotExist:
        messages.error(request, "Veuillez d'abord vous inscrire au programme partenaire.")
        return redirect('become_partner')
    
    questions = formation.questions
    current_index = partenaire.last_question_index
    
    # --- Vérifier si la formation est terminée ---
    if current_index >= len(questions):
        # Vérifier le score final pour déterminer le statut
        partenaire.status = 'completed' if partenaire.score >= 50 else 'rejected'
        partenaire.progression = 100
        partenaire.save()
        
        if partenaire.score >= 50:
            messages.success(request, f"Félicitations ! Vous avez terminé avec un score de {partenaire.score}%. En attente de validation.")
            return render(request, 'partners/training_complete.html', {'partenaire': partenaire})
        else:
            messages.error(request, f"Désolé, votre score final est de {partenaire.score}%, insuffisant pour la validation. Vous avez échoué.")
            return render(request, 'partners/training_failed.html', {'partenaire': partenaire})
    
    current_question_data = questions[current_index]
    total_questions = len(questions)
    
    # --- Gérer les tentatives ---
    MAX_ATTEMPTS = 2 # Exemple : 2 tentatives par question
    if request.method == 'POST':
        user_answer = request.POST.get('answer')
        correct_answer = current_question_data.get('answer')

        is_correct = False
        question_type = current_question_data.get('type')
        if question_type == 'choix_multiples':
            if user_answer == correct_answer:
                is_correct = True
        else:
            if user_answer and user_answer.strip().lower() == correct_answer.strip().lower():
                is_correct = True

        if is_correct:
            # Augmenter le score si la réponse est correcte
            partenaire.score += current_question_data.get('value', 0)
            partenaire.last_question_index += 1
            partenaire.failed_attempts = 0 # Réinitialiser les tentatives pour la question suivante
            partenaire.progression = int((partenaire.last_question_index / total_questions) * 100)
            partenaire.save()
            messages.success(request, "Bonne réponse ! Question suivante.")
            return redirect('training')
        else:
            partenaire.failed_attempts += 1
            partenaire.save()
            messages.error(request, f"Mauvaise réponse. Tentatives restantes : {MAX_ATTEMPTS - partenaire.failed_attempts}")
            
            if partenaire.failed_attempts >= MAX_ATTEMPTS:
                # Échec, passer à la question suivante mais sans gagner de points
                partenaire.last_question_index += 1
                partenaire.failed_attempts = 0
                partenaire.progression = int((partenaire.last_question_index / total_questions) * 100)
                partenaire.save()
                messages.warning(request, "Trop de mauvaises réponses. Vous passez à la question suivante.")
                return redirect('training')

    context = {
        'partenaire': partenaire,
        'formation': formation,
        'question_data': current_question_data,
        'current_question_number': current_index + 1,
        'total_questions': total_questions,
        'attempts_remaining': MAX_ATTEMPTS - partenaire.failed_attempts,
    }
    return render(request, 'partners/training.html', context)


#Derniere modification de renew je commente pour tester la pop-up de renouvellement


@login_required
def renew_contract_view(request):
    """
    Vue pour renouveler le contrat d'un partenaire.
    """
    try:
        partenaire = Partenaire.objects.get(user=request.user)
    except Partenaire.DoesNotExist:
        messages.error(request, "Vous n'êtes pas un partenaire valide.")
        return redirect('dashboard')
    
    if partenaire.status != 'validated':
        messages.warning(request, "Votre compte partenaire n'est pas encore validé.")
        return redirect('dashboard')
    
    # Renouvellement de 3 mois (environ 90 jours)
    partenaire.contract_end_date += timedelta(days=90)
    partenaire.save()
    
    messages.success(request, "Votre contrat a été renouvelé avec succès pour 3 mois supplémentaires !")
    return redirect('partner_dashboard')



@login_required
def request_withdrawal_view(request):
    """
    Vue pour soumettre une demande de retrait via un formulaire modal.
    """
    try:
        partenaire = Partenaire.objects.get(user=request.user)
    except Partenaire.DoesNotExist:
        messages.error(request, "Vous n'êtes pas un partenaire valide.")
        return redirect('dashboard')
    
    MIN_WITHDRAWAL_AMOUNT = Decimal('1000')

    if request.method == 'POST':
        form = WithdrawalRequestForm(request.POST)
        if form.is_valid():
            withdrawal_amount = form.cleaned_data['amount']
            payment_method = form.cleaned_data['payment_method']
            payment_details = form.cleaned_data['payment_details']
            
            if partenaire.balance < withdrawal_amount:
                messages.error(request, "Votre solde est insuffisant pour ce retrait.")
            elif withdrawal_amount < MIN_WITHDRAWAL_AMOUNT:
                 messages.error(request, f"Le montant minimum de retrait est de {MIN_WITHDRAWAL_AMOUNT} F CFA.")
            else:
                with transaction.atomic():
                    # 1. Créer la demande de retrait avec le montant, la méthode et les détails choisis
                    WithdrawalRequest.objects.create(
                        partenaire=partenaire,
                        amount=withdrawal_amount,
                        payment_method=payment_method,
                        payment_details=payment_details,
                    )
                    
                    # 2. Débiter le solde du partenaire
                    partenaire.balance -= withdrawal_amount
                    partenaire.save()
                    
                    # 3. Envoyer une notification par e-mail à l'administrateur
                    subject = f"Nouvelle demande de retrait de {request.user.username}"
                    message = (
                        f"Une nouvelle demande de retrait a été soumise :\n\n"
                        f"Partenaire : {request.user.username} ({request.user.email})\n"
                        f"Montant : {withdrawal_amount} F CFA\n"
                        f"Méthode de paiement : {payment_method}\n"
                        f"Détails du paiement : {payment_details}\n"
                    )
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL])
                    
                    messages.success(request, "Votre demande de retrait a été soumise avec succès.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    
    return redirect('partner_dashboard')




@login_required
def cancel_partner_contract_view(request):
    """
    Permet à un partenaire de résilier son contrat.
    """
    try:
        partenaire = Partenaire.objects.get(user=request.user)
        
        # Le statut 'cancelled' est plus précis que 'rejected' ou 'deactivated'
        partenaire.status = 'cancelled'
        partenaire.save()
        
        # Envoie un message de confirmation à l'utilisateur
        messages.success(request, "Votre contrat partenaire a été annulé avec succès. Nous sommes désolés de vous voir partir !")
        
    except Partenaire.DoesNotExist:
        messages.error(request, "Vous n'êtes pas un partenaire valide.")
        
    # Redirige l'utilisateur vers son tableau de bord principal après l'annulation
    return redirect('dashboard')