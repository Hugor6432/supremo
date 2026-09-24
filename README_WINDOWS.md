# P1 - Sistema de Reserva de Salas


### 1. Executar Comandos (COPIAR E COLAR)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 2. Acessar

Site: http://127.0.0.1:8000/
Admin: http://127.0.0.1:8000/admin/

## Credentials (Exemplo)

Username: admin
Password: admin123

## Para Parar

Pressione: Ctrl + C

## Funcionalidades P1

✅ CRUD Salas
✅ CRUD Reservas  
✅ CRUD Recorrências
✅ CRUD Recursos
✅ Validação de Conflito de Horário
✅ Busca e Filtro de Salas (nome/descrição, capacidade mínima, recurso)
✅ Validação: término da reserva depois do início
✅ Status: Pendente/Confirmada/Cancelada
✅ Recorrência: Diária/Semanal/Mensal
✅ Admin Django
✅ Interface com Bootstrap
