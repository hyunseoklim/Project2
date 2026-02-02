from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy


class LoginView(DjangoLoginView):
	template_name = "accounts/login.html"
	redirect_authenticated_user = True

	def get_success_url(self):
		return reverse_lazy("accounts:home")


class LogoutView(DjangoLogoutView):
	next_page = reverse_lazy("accounts:login")


@login_required
def home(request):
	return render(request, "accounts/home.html")


def signup(request):
	if request.method == "POST":
		form = UserCreationForm(request.POST)
		if form.is_valid():
			form.save()
			return redirect("accounts:login")
	else:
		form = UserCreationForm()

	return render(request, "accounts/signup.html", {"form": form})
