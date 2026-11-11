from django.db import migrations


def org_padrao(apps, schema_editor):
    # Registros já existentes vão para a "Organização padrão"
    Organizacao = apps.get_model('core', 'Organizacao')
    org, _ = Organizacao.objects.get_or_create(nome='Organização padrão')

    for nome_model in ['Sala', 'Recurso', 'Recorrencia', 'Reserva']:
        Model = apps.get_model('salas', nome_model)
        Model.objects.filter(organizacao__isnull=True).update(organizacao=org)


class Migration(migrations.Migration):

    dependencies = [
        ('salas', '0002_organizacao_nula'),
    ]

    operations = [
        migrations.RunPython(org_padrao, migrations.RunPython.noop),
    ]
