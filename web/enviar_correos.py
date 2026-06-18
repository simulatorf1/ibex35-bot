import os
import requests
from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Obtener notificaciones no enviadas
response = supabase.table('historial_notificaciones').select('*').eq('enviado_correo', False).execute()
notificaciones = response.data

if len(notificaciones) == 0:
    print('📭 No hay correos pendientes')
    exit(0)

print(f'📧 Enviando {len(notificaciones)} correos...')

for notif in notificaciones:
    # Obtener email del usuario
    user_response = supabase.table('perfiles').select('email').eq('id', notif['usuario_id']).execute()
    if not user_response.data:
        continue
    email = user_response.data[0]['email']
    
    # Enviar correo
    r = requests.post(
        'https://api.resend.com/emails',
        headers={
            'Authorization': f'Bearer {RESEND_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'from': 'notificaciones@resend.dev',
            'to': email,
            'subject': f'🔔 Alerta: {notif["nombre_empresa"]}',
            'html': f'<p>{notif["mensaje"]}</p>'
        }
    )
    
    if r.status_code == 200:
        supabase.table('historial_notificaciones').update({'enviado_correo': True}).eq('id', notif['id']).execute()
        print(f'✅ Enviado a {email}')
    else:
        print(f'❌ Error: {r.text}')
