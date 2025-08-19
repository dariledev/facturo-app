# core/models.py
from django.db import models, transaction, IntegrityError
import logging

import uuid # Pour les numéros de facture uniques
from datetime import date
from django.urls import reverse

from django.contrib.auth.models import AbstractUser
from datetime import timedelta
from django.db.models.fields.json import JSONField
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)

# Nouveau modèle utilisateur personnalisé
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, null=False, blank=False)
    email_confirmed = models.BooleanField(default=False)
    
    # --- NOUVEAUX CHAMPS POUR LA GESTION DE L'ESSAI ---
    is_trial_active = models.BooleanField(default=True)
    trial_start_date = models.DateTimeField(null=True, blank=True)
    trial_duration_days = models.IntegerField(default=2)
    is_paid_subscriber = models.BooleanField(default=False)
    commission_paid = models.BooleanField(default=False)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='filleuls')
    # Ajoutez des related_name uniques...
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name="customuser_groups",
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="customuser_permissions",
        related_query_name="customuser",
    )
    has_paid_subscription = models.BooleanField(default=False, verbose_name="Abonnement payant")
    
    @property
    def trial_end_date(self):
        if self.trial_start_date:
            return self.trial_start_date + timedelta(days=self.trial_duration_days)
        return None

    def __str__(self):
        return self.email
    
    @property
    def is_partner(self):
        try:
            return self.partenaire.status == 'validated'
        except Partenaire.DoesNotExist:
            return False


class CompanyProfile(models.Model):
    # Corriger ici : utiliser CustomUser
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='company_profile')
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Informations fiscales (TVA, SIRET...)")
    bank_details = models.TextField(blank=True, null=True, verbose_name="Coordonnées bancaires")
    default_payment_terms = models.TextField(blank=True, null=True, verbose_name="Conditions de paiement par défaut")

    def __str__(self):
        return self.name

class Client(models.Model):
    # Corriger ici : utiliser CustomUser
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='clients')
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField()
    tax_info = models.CharField(max_length=255, blank=True, null=True, verbose_name="Informations fiscales (SIRET, TVA intracommunautaire...)")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    # Corriger ici : utiliser CustomUser
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20.00, verbose_name="Taux de TVA (%)") # Exemple: 20.00%
    sku = models.CharField(max_length=50, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Brouillon'),
        ('Sent', 'Envoyée'),
        ('Paid', 'Payée'),
        ('Partially Paid', 'Partiellement payée'),
        ('Overdue', 'En retard'),
        ('Cancelled', 'Annulée'),
    ]

    # Corriger ici : utiliser CustomUser
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='invoices')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='invoices')
    company_profile = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                        help_text="Profil d'entreprise utilisé pour émettre cette facture")
    invoice_number = models.CharField(max_length=100, unique=True, editable=False)
    issue_date = models.DateField(default=date.today)
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Remise (%)")
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Frais de port")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True, null=True, verbose_name="Notes / Conditions de paiement")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    template = models.ForeignKey(
        'InvoiceTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Modèle de facture"
    )

    class Meta:
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f"Facture {self.invoice_number} pour {self.client.name}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = self.issue_date.year
            new_num = 1 # Numéro de séquence de départ

            logger.debug(f"Début génération numéro pour l'année: {year}. Utilisateur PK: {self.user.pk if self.user else 'None'}.")

            for attempt in range(1, 100): # Augmenter les tentatives pour plus de robustesse si nécessaire
                try:
                    with transaction.atomic():
                        # IMPORTANT: last_invoice est trouvé GLOBALEMENT, PAS par utilisateur
                        # Le verrouillage est sur les factures de l'année pour prévenir la concurrence.
                        # Utilisez 'invoice_number' pour le tri si c'est la séquence principale
                        last_invoice = Invoice.objects.select_for_update().filter(
                            issue_date__year=year
                        ).order_by('invoice_number').last() 

                        if last_invoice and last_invoice.invoice_number.startswith(f"INV-{year}-"):
                            try:
                                # Extrait le dernier numéro de la séquence INV-YYYY-NNNN
                                last_num_str = last_invoice.invoice_number.split('-')[-1]
                                last_num = int(last_num_str)
                                new_num = last_num + 1
                            except (ValueError, IndexError):
                                # Si le format est corrompu, on réinitialise à 1 ou au numéro suivant sûr.
                                logger.warning(f"Tentative {attempt}: Format de numéro inattendu pour {last_invoice.invoice_number}. Réinitialisation à 1.")
                                new_num = 1
                        else:
                            logger.debug(f"Tentative {attempt}: Aucune facture trouvée pour l'année {year}. Démarrage à 1.")
                            new_num = 1 # Aucune facture pour l'année, commence à 1
                        
                        proposed_invoice_number = f"INV-{year}-{new_num:04d}"
                        
                        # Vérification explicite de l'existence du numéro proposé (GLOBALEMENT)
                        if Invoice.objects.filter(invoice_number=proposed_invoice_number).exists():
                            logger.warning(f"Tentative {attempt}: Numéro {proposed_invoice_number} existe déjà globalement. Incrémente et réessaie.")
                            new_num += 1 # Incrémente et réessaie
                            continue # Passe à l'itération suivante de la boucle

                        self.invoice_number = proposed_invoice_number
                        logger.info(f"Numéro de facture généré avec succès: {self.invoice_number}")
                        break # Numéro unique trouvé, sortir de la boucle

                except IntegrityError:
                    # Cela peut arriver si deux processus tentent d'insérer le même numéro
                    # au même moment, après notre vérification. On incrémente et on réessaie.
                    new_num += 1
                    logger.warning(f"Tentative {attempt}: IntegrityError lors de la sauvegarde pour {proposed_invoice_number}. Réessaie avec {new_num}.")
                    continue
                except Exception as e:
                    logger.error(f"Erreur inattendue lors de la génération du numéro de facture: {e}", exc_info=True)
                    raise # Relance toute autre exception inattendue

            else: # Ce bloc s'exécute si la boucle se termine sans 'break'
                logger.critical(f"Échec critique: Impossible de générer un numéro de facture unique après {attempt} tentatives pour l'année {year}. Abandon.")
                raise Exception("Impossible de générer un numéro de facture unique après plusieurs tentatives. Veuillez contacter le support.")
            
        if not self.template_id: # Utiliser self.template_id pour éviter un accès à la DB
            try:
                self.template = InvoiceTemplate.objects.get(is_default=True)
            except InvoiceTemplate.DoesNotExist:
                # Si aucun template par défaut n'est trouvé, le champ reste vide (null)
                self.template = None
        # --- Fin de la nouvelle logique ---

        super().save(*args, **kwargs)

    def calculate_totals(self):
        """
        Calcule et met à jour le sous-total, le montant de la taxe, le montant total,
        et les frais de port de la facture basés sur ses articles.
        """
        subtotal = sum(item.total_price for item in self.items.all())
        self.subtotal = subtotal

        total_tax = sum(item.tax_amount for item in self.items.all())
        self.tax_amount = total_tax

        discount_amount = (self.subtotal * (self.discount / 100)) if self.discount is not None else 0.00
        subtotal_after_discount = self.subtotal - discount_amount

        self.total_amount = subtotal_after_discount + self.tax_amount + self.shipping_cost
        
        # Utilisez update_fields pour éviter une nouvelle boucle save() complète et ne sauvegarder que les champs pertinents.
        self.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])


    def get_absolute_url(self):
        return reverse('invoice_detail', kwargs={'pk': self.pk})


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                help_text="Produit/service du catalogue, si applicable")
    description = models.CharField(max_length=255, help_text="Description de l'article (si non lié à un produit)")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20.00) # Taux de TVA pour cet article
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0.00)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price}€)"


    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        self.tax_amount = self.total_price * (self.tax_rate / 100)
        super().save(*args, **kwargs)
        self.invoice.calculate_totals() # Met à jour les totaux de la facture parente

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.calculate_totals() # Recalcule les totaux après suppression d'un article




class InvoiceTemplate(models.Model):
    """
    Modèle représentant un template de facture que l'utilisateur peut choisir.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom du modèle")
    template_file = models.CharField(max_length=255, verbose_name="Chemin du fichier template")
    is_default = models.BooleanField(default=False, verbose_name="Utiliser par défaut")
    preview_image = models.ImageField(upload_to='template_previews/', blank=True, null=True, verbose_name="Aperçu du modèle")
    def __str__(self):
        return self.name
    




class Formation(models.Model):
    """
    Modèle pour la formation des partenaires.
    """
    title = models.CharField(max_length=200, verbose_name="Titre de la formation")
    description = models.TextField(verbose_name="Description du programme")
    questions = JSONField(verbose_name="Questions de la formation (format JSON)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    

class Partenaire(models.Model):
    """
    Modèle représentant un partenaire commercial.
    """
    STATUS_CHOICES = [
        ('in_progress', 'En formation'),
        ('completed', 'Formation terminée'),
        ('validated', 'Validé'),
        ('rejected', 'Rejeté'),
        ('cancelled', 'Annulé'),  # <-- AJOUTEZ CETTE LIGNE
    ]

    user = models.OneToOneField('CustomUser', on_delete=models.CASCADE, verbose_name="Utilisateur")
    formation = models.ForeignKey(Formation, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress', verbose_name="Statut")
    progression = models.IntegerField(default=0, verbose_name="Progression (%)")
    last_question_index = models.IntegerField(default=0, verbose_name="Index de la dernière question")
    validated_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_partners', verbose_name="Validé par")
    contract_start_date = models.DateField(null=True, blank=True, verbose_name="Date de début du contrat")
    created_at = models.DateTimeField(auto_now_add=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="Score")
    failed_attempts = models.IntegerField(default=0, verbose_name="Tentatives échouées")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Taux de commission (%)")
    contract_start_date = models.DateField(null=True, blank=True, verbose_name="Date de début du contrat")
    contract_end_date = models.DateField(null=True, blank=True, verbose_name="Date de fin du contrat")
    referral_code = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Code de parrainage")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    def save(self, *args, **kwargs):
        # Récupérer l'état de l'objet avant la sauvegarde, s'il existe
        try:
            old_instance = Partenaire.objects.get(pk=self.pk)
        except Partenaire.DoesNotExist:
            old_instance = None

        # Logique pour le code de parrainage
        if not self.referral_code and self.status == 'validated':
            self.referral_code = str(uuid.uuid4()).split('-')[0].upper()

        # Nouvelle logique pour la date de contrat
        # On vérifie si le statut a changé pour 'validated'
        if old_instance and old_instance.status != 'validated' and self.status == 'validated':
            self.contract_start_date = timezone.now().date()
            self.contract_end_date = self.contract_start_date + timedelta(days=90) # 3 mois

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Partenaire: {self.user.username} - Statut: {self.get_status_display()}"
    



class MarketingMaterial(models.Model):
    """
    Modèle pour les supports marketing téléchargeables par les partenaires.
    """
    title = models.CharField(max_length=200, verbose_name="Titre du support")
    description = models.TextField(blank=True, verbose_name="Description")
    file = models.FileField(upload_to='marketing_materials/', verbose_name="Fichier")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Support marketing"
        verbose_name_plural = "Supports marketing"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
    )
    
    PAYMENT_METHODS = (
        ('airtel_money', 'Airtel Money'),
        ('bank_transfer', 'Virement Bancaire'),
    )
    
    partenaire = models.ForeignKey(Partenaire, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default='orange_money') # Ajout du champ pour la méthode de paiement
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending') # Utilisation d'un statut plus clair
    request_date = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateTimeField(null=True, blank=True)
    payment_details = models.CharField(max_length=255, help_text="Numéro de téléphone ou informations bancaires pour le paiement.")

    def __str__(self):
        return f"Demande de {self.amount} FCFA par {self.partenaire.user.username}"