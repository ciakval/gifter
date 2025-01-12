from django.shortcuts import render
from django.http import HttpResponse
from django.views import View
from .models import Wish
from .forms import WishForm

# Create your views here.
class CreateWishView(View):
    def get(self, request):
        form = WishForm()
        return render(request, 'gifter/create_wish.html', {'form': form})

    def post(self, request):
        form = WishForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponse('Wish created successfully')
        return render(request, 'gifter/create_wish.html', {'form': form})