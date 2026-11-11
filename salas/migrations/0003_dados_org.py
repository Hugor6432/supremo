from django.db import migrations


def org_padrao(apps, schema_editor):
    """Etapa 2: os registros da P1 ficam na "Organização padrão".

    Usa apps.get_model (e não import direto) para enxergar os models
    como eles eram neste ponto das migrações.
    """
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
