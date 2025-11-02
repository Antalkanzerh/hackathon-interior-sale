from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect

from .forms import NewItemForm, EditItemForm
from .models import Category, Item, Tag


# mapping of category code/name to complementary categories (by name)
COMPLEMENTARY = {
    'Диваны и кресла': ['Столы и стулья', 'Ковры и текстиль', 'Декор'],
    'Ковры и текстиль': ['Диваны и кресла', 'Кровати и матрасы', 'Декор'],
    'Столы и стулья': ['Диваны и кресла', 'Освещение', 'Декор'],
    'Шкафы и стеллажи': ['Декор', 'Освещение'],
    'Кровати и матрасы': ['Ковры и текстиль', 'Декор'],
    'Освещение': ['Столы и стулья', 'Декор'],
    'Декор': ['Диваны и кресла', 'Столы и стулья', 'Кровати и матрасы'],
}

def items(request):
    query = request.GET.get('query', '')
    category_id = request.GET.get('category', 0)
    category_name = request.GET.get('category_name')
    categories = Category.objects.all()
    items = Item.objects.filter(is_sold=False)

    # filter by explicit category id or by category_name token (derived from image filenames or labels)
    if category_id:
        items = items.filter(category_id=category_id)
    if category_name:
        # match by image filename, item name, or tags
        items = items.filter(
            Q(image__icontains=category_name) | Q(name__icontains=category_name) | Q(tags__name__icontains=category_name)
        ).distinct()

    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query))

    return render(request, 'item/items.html', {
        'items': items,
        'query': query,
        'categories': categories,
        'category_id': int(category_id)
    })

def detail(request, pk):
    item = get_object_or_404(Item, pk=pk)

    # Recommendation algorithm: find complementary items rather than just same-category
    candidates = Item.objects.filter(is_sold=False).exclude(pk=pk).select_related('category')

    # narrow candidates to those that share style or tags or price-group tag or same color
    base_tags = set([t.name for t in item.tags.all()])
    base_style = item.style
    base_color = (item.color or '').lower()
    base_price = item.price_tg or 0

    # helper: color complementarity
    NEUTRALS = {'black', 'white', 'gray', 'beige', 'brown'}
    COMPLEMENTS = {
        'blue': ['orange', 'beige'],
        'orange': ['blue', 'beige'],
        'red': ['green', 'beige'],
        'green': ['red', 'beige'],
        'yellow': ['blue', 'beige'],
        'beige': ['blue', 'orange', 'brown'],
    }

    def color_compat_score(a, b):
        if not a or not b:
            return 0
        a = a.lower(); b = b.lower()
        if a == b:
            return 10
        if a in NEUTRALS or b in NEUTRALS:
            return 6
        if b in COMPLEMENTS.get(a, []):
            return 7
        return 0

    # size compatibility: same size preferred, adjacent size OK
    SIZE_PREF = {
        ('S', 'S'): 8,
        ('M', 'M'): 8,
        ('L', 'L'): 8,
        ('S', 'M'): 4,
        ('M', 'S'): 4,
        ('M', 'L'): 4,
        ('L', 'M'): 4,
    }

    scored = []
    for cand in candidates:
        score = 0
        comp = COMPLEMENTARY.get(item.category.name, []) if item.category else []

        # complementary category bonus
        if item.category and cand.category and cand.category.name in comp:
            score += 40

        # style match
        if base_style and cand.style == base_style:
            score += 20

        # shared tags
        cand_tags = set([t.name for t in cand.tags.all()])
        inter = base_tags.intersection(cand_tags)
        score += len(inter) * 8

        # color compatibility
        score += color_compat_score(base_color, cand.color)

        # size compatibility
        if item.size_category and cand.size_category:
            score += SIZE_PREF.get((item.size_category, cand.size_category), 0)

        # price proximity
        if cand.price_tg and base_price > 0:
            diff = abs(cand.price_tg - base_price)
            if diff < max(1, base_price * 0.1):
                score += 8
            elif diff < max(1, base_price * 0.25):
                score += 4

        # minor boost if different category (but not complementary)
        if item.category and cand.category and cand.category != item.category and cand.category.name not in comp:
            score += 5

        if score > 0:
            scored.append((score, cand))

    scored.sort(key=lambda x: x[0], reverse=True)
    related_items = [c for s, c in scored[:6]]

    return render(request, 'item/detail.html', {
        'item': item,
        'related_items': related_items
    })


def cart_view(request):
    cart = request.session.get('cart', {})
    item_ids = list(cart.keys())
    items = Item.objects.filter(id__in=item_ids)
    total = 0
    cart_items = []
    for it in items:
        qty = cart.get(str(it.id), 0)
        subtotal = (it.price_tg or 0) * qty
        total += subtotal
        cart_items.append({'item': it, 'qty': qty, 'subtotal': subtotal})

    return render(request, 'item/cart.html', {'cart_items': cart_items, 'total': total})


def cart_add(request, pk):
    # add one item to cart and redirect back
    item = get_object_or_404(Item, pk=pk)
    cart = request.session.get('cart', {})
    cart[str(item.id)] = cart.get(str(item.id), 0) + 1
    request.session['cart'] = cart
    return redirect('item:detail', pk=pk)


def cart_remove(request, pk):
    cart = request.session.get('cart', {})
    cart.pop(str(pk), None)
    request.session['cart'] = cart
    return redirect('item:cart')


def cart_update(request, pk):
    qty = int(request.POST.get('qty', 1))
    cart = request.session.get('cart', {})
    if qty <= 0:
        cart.pop(str(pk), None)
    else:
        cart[str(pk)] = qty
    request.session['cart'] = cart
    return redirect('item:cart')

@login_required
def new(request):
    if request.method == 'POST':
        form = NewItemForm(request.POST, request.FILES)

        if form.is_valid():
            item = form.save(commit=False)
            item.created_by = request.user
            item.save()

            return redirect('item:detail', pk=item.id)
    else:
        form = NewItemForm()

    return render(request, 'item/form.html', {
        'form': form,
        'title': 'New item',
    })

@login_required
def edit(request, pk):
    item = get_object_or_404(Item, pk=pk, created_by=request.user)

    if request.method == 'POST':
        form = EditItemForm(request.POST, request.FILES, instance=item)

        if form.is_valid():
            form.save()

            return redirect('item:detail', pk=item.id)
    else:
        form = EditItemForm(instance=item)

    return render(request, 'item/form.html', {
        'form': form,
        'title': 'Edit item',
    })

@login_required
def delete(request, pk):
    item = get_object_or_404(Item, pk=pk, created_by=request.user)
    item.delete()

    return redirect('dashboard:index')