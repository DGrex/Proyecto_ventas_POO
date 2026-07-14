import requests
from django.conf import settings


import time
import requests
from django.conf import settings

# Caché simple en memoria del proceso: PayPal entrega tokens válidos por
# ~9 horas (32000 seg), pero antes se pedía uno nuevo en CADA clic (crear
# orden + capturar orden), lo que sumaba ~0.5-1 seg de espera de más cada
# vez y era justo lo que se veía como el popup de PayPal "en blanco".

_token_cache = {'access_token': None, 'expires_at': 0}


def get_access_token():
    """Obtiene un token OAuth2 de acceso contra la API de PayPal (con caché)."""
    if _token_cache['access_token'] and time.time() < _token_cache['expires_at']:
        return _token_cache['access_token']

    url = f'{settings.PAYPAL_API_BASE}/v1/oauth2/token'
    response = requests.post(
        url,
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
        data={'grant_type': 'client_credentials'},
        headers={'Accept': 'application/json', 'Accept-Language': 'es_ES'},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    # Restamos 60 seg de margen de seguridad antes de que expire de verdad.
    _token_cache['access_token'] = data['access_token']
    _token_cache['expires_at'] = time.time() + data.get('expires_in', 32000) - 60
    return _token_cache['access_token']


def create_order(amount, currency='USD', reference_id=None):
    """
    Crea una orden de pago en PayPal por el monto indicado.
    Devuelve el JSON completo de la orden (incluye 'id' de la orden).
    """
    token = get_access_token()
    url = f'{settings.PAYPAL_API_BASE}/v2/checkout/orders'

    purchase_unit = {
        'amount': {
            'currency_code': currency,
            'value': f'{amount:.2f}',
        }
    }
    if reference_id:
        purchase_unit['reference_id'] = str(reference_id)

    payload = {
        'intent': 'CAPTURE',
        'purchase_units': [purchase_unit],
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def capture_order(order_id):
    """
    Captura (finaliza) una orden ya aprobada por el comprador.
    Devuelve el JSON completo de la captura, incluyendo el estado y el monto capturado.
    """
    token = get_access_token()
    url = f'{settings.PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture'

    response = requests.post(
        url,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()