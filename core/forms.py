# core/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Client, Product, CompanyProfile, Invoice, InvoiceItem, CustomUser, InvoiceTemplate, WithdrawalRequest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password # Pour réutiliser certains validateurs si souhaité
from django.contrib.auth.password_validation import CommonPasswordValidator, NumericPasswordValidator, UserAttributeSimilarityValidator, MinimumLengthValidator 


User = get_user_model()

# Nouveau formulaire d'inscription
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Requis. Doit être unique.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',) # Ajoutez l'email aux champs


class SupportForm(forms.Form):
    subject = forms.CharField(max_length=200, label="Objet du message")
    message = forms.CharField(widget=forms.Textarea, label="Votre message")



# --- Nouveau formulaire que nous allons utiliser pour l'inscription ---
class CleanUserRegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Nom d\'utilisateur'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Votre adresse email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe'})
    )
    password2 = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmer le mot de passe'})
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("Ce nom d'utilisateur est déjà pris.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cette adresse e-mail est déjà utilisée.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')

        if password and password2 and password != password2:
            self.add_error('password2', "Les deux mots de passe ne correspondent pas.")
        
        # --- PERSONNALISATION DES VALIDATEURS DE MOT DE PASSE ---
        # Ici, vous pouvez choisir d'appliquer CERTAINS validateurs ou d'écrire les vôtres.
        # Pour masquer les messages détaillés, nous ne levons PAS d'erreurs champ par champ ici
        # mais on peut les vérifier si on veut appliquer des règles sans montrer le détail.
        
        # Exemple: Appliquer une longueur minimale sans message détaillé sur le champ
        if password and len(password) < 8:
            # Vous pouvez choisir d'ajouter une erreur non-champ si vous le souhaitez
            # self.add_error(None, "Le mot de passe doit contenir au moins 8 caractères.")
            # Ou laisser le modèle User gérer la validation au moment du save()
            pass # On laisse la validation se faire plus tard ou on met un message général

        # Si vous voulez désactiver toutes les validations "complexes" de Django:
        # Ne faites RIEN ici en dehors de la vérification de correspondance.
        # Les validateurs par défaut (similitude, commun, numérique) ne seront pas appelés
        # par ce formulaire. Ils seront cependant appelés par le modèle User si configurés
        # via AUTH_PASSWORD_VALIDATORS dans settings.py lors du .save().

        return cleaned_data

    def save(self, commit=True):
        # Cette méthode est nécessaire car c'est un forms.Form, pas un ModelForm
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            is_active=False # Gardez cette logique pour l'activation par email
        )
        if commit:
            user.save()
        return user






''' 
# Nouveau formulaire d'authentification (peut être conservé tel quel si vous utilisez la vue de Django)
class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'password'] # Ou 'email', 'password' si vous voulez vous connecter avec l'email

'''
class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'contact_person', 'email', 'phone', 'address', 'tax_info', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'unit_price', 'tax_rate', 'sku']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ['name', 'logo', 'address', 'phone', 'email', 'tax_id', 'bank_details', 'default_payment_terms']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'bank_details': forms.Textarea(attrs={'rows': 3}),
            'default_payment_terms': forms.Textarea(attrs={'rows': 3}),
        }


class InvoiceForm(forms.ModelForm):
    # --- NOUVEAU CHAMP ---
    template = forms.ModelChoiceField(
        queryset=InvoiceTemplate.objects.all(),
        label="Modèle de Facture",
        empty_label=None,
        required=False, # Il est important que ce soit False, car la vue gère la valeur par défaut
    )

    class Meta:
        model = Invoice
        # Assurez-vous d'ajouter 'template' à la liste des champs
        fields = ['client', 'company_profile', 'issue_date', 'due_date', 'status', 'discount', 'shipping_cost', 'notes', 'template']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['client'].queryset = Client.objects.filter(user=user)
            self.fields['company_profile'].queryset = CompanyProfile.objects.filter(user=user)


class InvoiceItemForm(forms.ModelForm):
    product_choice = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        required=False,
        label="Choisir un produit existant",
        empty_label="--- Non lié à un produit ---"
    )

    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price', 'tax_rate']
        widgets = {
            'description': forms.TextInput(attrs={'placeholder': 'Description de l\'article', 'class': 'input'}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'class': 'input'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'class': 'input'}),
            'tax_rate': forms.NumberInput(attrs={'step': '0.01', 'class': 'input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['product_choice'].queryset = Product.objects.filter(user=user)
        
        # Ajouter les classes Bulma aux widgets ici aussi
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.Textarea, forms.EmailInput, forms.URLInput, forms.PasswordInput)):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' select'
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' checkbox'
            # Gérer le widget DateInput si utilisé (pour issue_date, due_date)
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' input'


        if self.instance.pk:
            if self.instance.product:
                self.fields['product_choice'].initial = self.instance.product
                self.fields['description'].required = False
                self.fields['unit_price'].initial = self.instance.product.unit_price
                self.fields['tax_rate'].initial = self.instance.product.tax_rate
            else:
                self.fields['description'].required = True

    def clean(self):
        cleaned_data = super().clean()
        product_choice = cleaned_data.get('product_choice')
        description = cleaned_data.get('description')

        if product_choice:
            cleaned_data['description'] = product_choice.name
            cleaned_data['unit_price'] = product_choice.unit_price
            cleaned_data['tax_rate'] = product_choice.tax_rate
            self.instance.product = product_choice
        elif not description:
            self.add_error('description', 'La description est requise si aucun produit n\'est sélectionné.')
        return cleaned_data

InvoiceItemFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    fields=['product_choice', 'description', 'quantity', 'unit_price', 'tax_rate'],
    extra=1,
    can_delete=True
)

# Formset pour gérer plusieurs InvoiceItems sur une seule page
InvoiceItemFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    fields=['product_choice', 'description', 'quantity', 'unit_price', 'tax_rate'],
    extra=1, # Nombre de formulaires vides à afficher
    can_delete=True
)



class WithdrawalRequestForm(forms.ModelForm):
    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'payment_method', 'payment_details']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'input', 'placeholder': 'Montant'}),
            'payment_method': forms.Select(attrs={'class': 'select is-fullwidth'}),
            'payment_details': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Votre numéro de téléphone ou de compte bancaire'})
        }

