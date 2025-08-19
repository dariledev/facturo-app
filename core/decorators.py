from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone

def trial_required(view_func):
    def wrapper_func(request, *args, **kwargs):
        # La vérification ne se fait que pour les utilisateurs actifs
        if request.user.is_authenticated and request.user.is_active:
            # Si l'essai est actif, mais qu'il a expiré, on le désactive
            if request.user.is_trial_active and request.user.trial_end_date and timezone.now() > request.user.trial_end_date:
                request.user.is_trial_active = False
                request.user.save()
                messages.error(request, "Votre période d'essai est terminée. Veuillez contacter l'administrateur pour réactiver votre compte.")
                return redirect('trial_expired')
            
            # Si l'essai n'est pas actif (même s'il n'a pas expiré), on redirige
            if not request.user.is_trial_active:
                messages.error(request, "Votre période d'essai est terminée. Veuillez contacter l'administrateur pour réactiver votre compte.")
                return redirect('trial_expired')
            
            return view_func(request, *args, **kwargs)
        else:
            return redirect('login') # Rediriger vers la page de connexion si l'utilisateur n'est pas authentifié

    return wrapper_func