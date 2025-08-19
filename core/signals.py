# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, Partenaire

@receiver(post_save, sender=CustomUser)
def update_partner_balance(sender, instance, created, **kwargs):
    """
    Incrémente le solde du partenaire si un utilisateur devient un abonné payant.
    """
    if instance.is_paid_subscriber and instance.referred_by:
        if hasattr(instance.referred_by, 'partenaire'):
            partner_profile = instance.referred_by.partenaire
            
            commission_rate = partner_profile.commission_rate
            revenue_per_client = Decimal('6500')
            commission_amount = (revenue_per_client * commission_rate) / Decimal('100')
            
            partner_profile.balance += commission_amount
            partner_profile.save(update_fields=['balance'])
            
            print(f"DEBUG: Solde du partenaire {partner_profile.user.username} mis à jour : +{commission_amount} FCFA.")


@receiver(post_save, sender=Partenaire)
def set_contract_dates_on_validation(sender, instance, created, **kwargs):
    """
    Définit la date de début et de fin de contrat la première fois que le statut est "validated".
    """
    if not created: # On agit seulement sur une mise à jour d'un objet existant
        try:
            old_instance = Partenaire.objects.get(pk=instance.pk)
            # Vérifier si le statut vient de passer à 'validated'
            if old_instance.status != 'validated' and instance.status == 'validated':
                instance.contract_start_date = timezone.now()
                instance.contract_end_date = timezone.now() + timedelta(days=90)
                # Sauvegarde l'instance avec les nouveaux champs pour éviter une boucle de signal
                instance.save(update_fields=['contract_start_date', 'contract_end_date', 'status'])
        except Partenaire.DoesNotExist:
            # Ne rien faire si l'objet n'existe pas
            pass


'''
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from .models import CustomUser, Partenaire

@receiver(post_save, sender=CustomUser)
def update_partner_balance(sender, instance, created, **kwargs):
    """
    Incrémente le solde du partenaire si un utilisateur devient un abonné payant.
    """
    # Vérifie si l'utilisateur est maintenant un abonné payant
    # et s'il a un parrain
    if instance.is_paid_subscriber and instance.referred_by:
        # Assurez-vous que le parrain est bien un partenaire
        if hasattr(instance.referred_by, 'partenaire'):
            partner_profile = instance.referred_by.partenaire
            
            # Calcule la commission en fonction du taux du partenaire
            commission_rate = partner_profile.commission_rate
            revenue_per_client = Decimal('6500')
            commission_amount = (revenue_per_client * commission_rate) / Decimal('100')
            
            # Mise à jour du solde du partenaire
            partner_profile.balance += commission_amount
            partner_profile.save(update_fields=['balance'])
            
            print(f"DEBUG: Solde du partenaire {partner_profile.user.username} mis à jour : +{commission_amount} FCFA.")


'''