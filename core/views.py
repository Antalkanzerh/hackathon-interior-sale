from django.shortcuts import render, redirect
from item.models import Category, Item
from .forms import SignupForm

def index(request):
    items = Item.objects.filter(is_sold=False).select_related('category')[:6]
    
    # Простой алгоритм сочетаемости — похожие товары по категории
    for item in items:
        item.matches = Item.objects.filter(category=item.category).exclude(id=item.id)[:3]
    
    categories = Category.objects.all()

    return render(request, 'core/index.html', {
        'categories': categories,
        'items': items,
    })

def contact(request):
    return render(request, 'core/contact.html')

def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('/login/')
    else:
        form = SignupForm()

    return render(request, 'core/signup.html', {'form': form})
