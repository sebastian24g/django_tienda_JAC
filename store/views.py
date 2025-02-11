from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
import json
import datetime
from .models import *
from .utils import cookieCart, cartData, guestOrder
import urllib.parse

def welcome(request):
    """
    Vista de bienvenida para la página principal.
    """
    return render(request, 'store/welcome.html')

def store(request):
    data = cartData(request)
    cartItems = data['cartItems']
    products = Product.objects.all()
    context = {'products': products, 'cartItems': cartItems}
    return render(request, 'store/store.html', context)

def cart(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']
    context = {'items': items, 'order': order, 'cartItems': cartItems}
    return render(request, 'store/cart.html', context)

def checkout(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']
    context = {'items': items, 'order': order, 'cartItems': cartItems}
    return render(request, 'store/checkout.html', context)

def updateItem(request):
    try:
        data = json.loads(request.body)
        productId = data['productId']
        action = data['action']

        # Verificar si el usuario tiene un Customer
        customer = getattr(request.user, 'customer', None)
        if not customer:
            return JsonResponse({'error': 'El usuario no tiene un perfil de cliente'}, status=400)

        product = get_object_or_404(Product, id=productId)
        order, created = Order.objects.get_or_create(customer=customer, complete=False)

        orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

        if action == 'add':
            orderItem.quantity += 1
            product.quantity -= 1
        elif action == 'remove':
            orderItem.quantity -= 1
            product.quantity += 1

        orderItem.save()
        product.save()

        if orderItem.quantity <= 0:
            orderItem.delete()

        return JsonResponse('Item was added', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def processOrder(request):
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)

    if request.user.is_authenticated:
        # Usuario autenticado
        customer, created = Customer.objects.get_or_create(user=request.user)
    else:
        # Usuario NO autenticado (invitado)
        email = data['form']['email']
        customer, created = Customer.objects.get_or_create(email=email)
    
    # Actualizar datos del cliente si se crearon recientemente
    if created or not customer.name:
        customer.name = data['form']['name']
        customer.phone = data['form']['phone']
        customer.address = data['shipping']['address']
        customer.city = data['shipping']['city']
        customer.save()

    # Crear la orden asociada al cliente sin sobrescribir otras
    order, created = Order.objects.get_or_create(customer=customer, complete=False)
    
    total = float(data['form']['total'])
    order.transaction_id = transaction_id

    # Validar el total antes de marcar la orden como completa
    if total == order.get_cart_total:
        order.complete = True
        for item in order.orderitem_set.all():
            product = item.product
            product.quantity -= item.quantity
            product.save()
    
    order.save()

    # Guardar la dirección de envío si aplica
    if order.shipping:
        ShippingAddress.objects.create(
            customer=customer,
            order=order,
            address=data['shipping']['address'],
            city=data['shipping']['city'],
        )

    # **Generar el mensaje de WhatsApp**
    message = f"Nuevo pedido de {customer.name}. Total: ${order.get_cart_total}. Detalles del pedido:\n"
    for item in order.orderitem_set.all():
        message += f"{item.quantity} x {item.product.name} - ${item.get_total}\n"
    message += f"\nDirección de envío: {data['shipping']['address']}, {data['shipping']['city']}"
    message += f"\n\nDatos del comprador:\nNombre: {data['form']['name']}\nTeléfono: {data['form']['phone']}\nDescripción: {data['shipping']['description']}"

    # **Codificar el mensaje para la URL de WhatsApp**
    encoded_message = urllib.parse.quote(message)
    whatsapp_url = f"https://wa.me/+573243442837?text={encoded_message}"

    # **Limpiar el carrito y redirigir a WhatsApp**
    response = JsonResponse({'whatsapp_url': whatsapp_url}, safe=False)
    if not request.user.is_authenticated:
        response.delete_cookie('cart')

    return response
