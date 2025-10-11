from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)  # importante pasar request
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth_login(request, user)                  # <— usamos el alias
                messages.success(request, '¡Bienvenido!')
                return redirect('Principal')               # o al dashboard
            else:
                messages.error(request, 'Usuario o contraseña incorrectos.')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

def logout_confirm(request):
    # Muestra una página con la confirmacion
    return render(request, 'accounts/logout_confirm.html')

def logout_view(request):
    auth_logout(request)                                   
    return redirect('Principal')
