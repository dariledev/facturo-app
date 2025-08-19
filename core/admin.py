from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from datetime import date, timedelta
from django.db.models.fields.json import JSONField 
from django.forms import widgets
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
from .models import *
from django.contrib import messages

@admin.register(MarketingMaterial)
class MarketingMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_at')
    search_fields = ('title',)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('is_trial_active', 'trial_start_date', 'trial_end_date',)
    list_filter = UserAdmin.list_filter + ('is_trial_active',)
    fieldsets = UserAdmin.fieldsets + (
        ('Informations sur la période d\'essai', {'fields': ('is_trial_active', 'trial_start_date', 'trial_duration_days')}),
    )

    # Combinez les actions dans une seule liste
    actions = ['mark_as_paid_subscriber', 'activate_trial']
    
    def mark_as_paid_subscriber(self, request, queryset):
        for user in queryset:
            # S'assure de ne pas déclencher le signal si l'utilisateur est déjà payant
            if not user.is_paid_subscriber:
                user.is_paid_subscriber = True
                user.save(update_fields=['is_paid_subscriber'])
        self.message_user(request, "Les utilisateurs sélectionnés ont été marqués comme abonnés payants.")
    
    mark_as_paid_subscriber.short_description = "Marquer comme abonné payant"
    
    def trial_end_date(self, obj):
        return obj.trial_end_date
    trial_end_date.short_description = "Fin de l'essai"

    def activate_trial(self, request, queryset):
        queryset.update(is_trial_active=True, trial_start_date=timezone.now())
        self.message_user(request, "La période d'essai pour les utilisateurs sélectionnés a été réactivée.")
    activate_trial.short_description = "Réactiver l'essai pour les utilisateurs sélectionnés"

@admin.register(InvoiceTemplate)
class InvoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_file', 'is_default')
    list_filter = ('is_default',)
    search_fields = ('name',)
    list_editable = ('is_default',) 

@admin.register(Partenaire)
class PartenaireAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'progression', 'contract_start_date', 'contract_end_date', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username',)
    readonly_fields = ('progression', 'last_question_index', 'created_at', 'score', 'failed_attempts')
    actions = ['validate_partner', 'reject_partner']

    def validate_partner(self, request, queryset):
        for partenaire in queryset:
            print(f"DEBUG: Tâche de validation pour le partenaire {partenaire.user.username}")
            print(f"DEBUG: Statut actuel: {partenaire.status}, Score: {partenaire.score}")
            
            if partenaire.status == 'completed' and partenaire.score >= 50:
                print("DEBUG: Condition de validation remplie. Tentative d'envoi d'email.")
                
                partenaire.status = 'validated'
                partenaire.validated_by = request.user
                partenaire.contract_start_date = date.today()
                partenaire.contract_end_date = date.today() + timedelta(days=365)
                partenaire.commission_rate = Decimal('30.00')
                partenaire.save()
                
                partner_dashboard_url = request.build_absolute_uri(reverse('partner_dashboard'))
                
                email_context = {
                    'partenaire': partenaire,
                    'partner_dashboard_url': partner_dashboard_url,
                }
                
                subject = "Bienvenue dans le programme partenaire Facturo !"
                html_message = render_to_string('emails/partner_contract_email.html', email_context)
                plain_message = strip_tags(html_message)
                from_email = settings.DEFAULT_FROM_EMAIL
                to = partenaire.user.email
                
                try:
                    send_mail(subject, plain_message, from_email, [to], html_message=html_message)
                    print("DEBUG: Email envoyé avec succès.")
                except Exception as e:
                    print(f"ERREUR D'ENVOI D'EMAIL: {e}")
                    messages.error(request, f"Erreur lors de l'envoi de l'email à {partenaire.user.username}: {e}")
            else:
                print("DEBUG: Condition de validation non remplie. Email non envoyé.")
                messages.warning(request, f"Le partenaire {partenaire.user.username} n'a pas été validé car le statut ou le score est incorrect.")

        self.message_user(request, "Traitement des partenaires terminé. Vérifiez les logs pour les détails.")
    validate_partner.short_description = "Valider les partenaires sélectionnés"

    def reject_partner(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, "Partenaires rejetés avec succès.")
    reject_partner.short_description = "Rejeter les partenaires sélectionnés"

@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title',)
    formfield_overrides = {
        JSONField: {'widget': widgets.Textarea},
    }

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('partner_user', 'amount', 'request_date', 'is_paid', 'paid_date')
    list_filter = ('is_paid', 'request_date')
    search_fields = ('partner__user__username', 'partner__user__email')
    actions = ['mark_as_paid']

    def partner_user(self, obj):
        return obj.partner.user.username
    partner_user.short_description = 'Partenaire'

    def mark_as_paid(self, request, queryset):
        updated_count = queryset.filter(is_paid=False).update(is_paid=True, paid_date=timezone.now())
        
        if updated_count == 1:
            message_bit = "1 demande a été marquée comme payée."
        else:
            message_bit = f"{updated_count} demandes ont été marquées comme payées."
            
        self.message_user(request, message_bit)
        
    mark_as_paid.short_description = "Marquer les demandes sélectionnées comme payées"

# Enregistrement des modèles sans classe d'admin personnalisée
admin.site.register(CompanyProfile)
admin.site.register(InvoiceItem)
admin.site.register(Invoice)
admin.site.register(Client) 
admin.site.register(Product)