from django.db import migrations


def org_padrao(apps, schema_editor):
    # Registros já existentes (dados da P1) vão para a "Organização padrão".
    # Num banco novo não há registros, então a organização não é criada.
    sem_org = [
        apps.get_model('salas', nome_model).objects.filter(organizacao__isnull=True)
        for nome_model in ['Sala', 'Recurso', 'Recorrencia', 'Reserva']
    ]
    if not any(qs.exists() for qs in sem_org):
        return

    Organizacao = apps.get_model('core', 'Organizacao')
    org, _ = Organizacao.objects.get_or_create(nome='Organização padrão')
    for qs in sem_org:
        qs.update(organizacao=org)


class Migration(migrations.Migration):

    dependencies = [
        ('salas', '0002_organizacao_nula'),
    ]

    operations = [
        migrations.RunPython(org_padrao, migrations.RunPython.noop),
    ]
