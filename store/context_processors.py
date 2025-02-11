from .utils import cartData

def cart(request):
    """
    Procesador de contexto para agregar el carrito de compras a todas las plantillas.
    """
    data = cartData(request)
    return {
        'cartItems': data['cartItems']
    }