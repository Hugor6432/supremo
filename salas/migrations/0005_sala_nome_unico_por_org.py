from django.db import migrations, models


def renomeia_duplicadas(apps, schema_editor):
    """Se já houver salas com o mesmo nome na mesma organização (dados da P1),
    acrescenta " (2)", " (3)"... para a restrição de unicidade não falhar."""
    Sala = apps.get_model('salas', 'Sala')
    vistos = set()
    for sala in Sala.objects.order_by('id'):
        chave = (sala.organizacao_id, sala.nome)
        if chave in vistos:
            n = 2
            while (sala.organizacao_id, f"{sala.nome} ({n})") in vistos:
                n += 1
            sala.nome = f"{sala.nome} ({n})"
            sala.save(update_fields=['nome'])
        vistos.add((sala.organizacao_id, sala.nome))


class Migration(migrations.Migration):

    dependencies = [
        ('salas', '0004_organizacao_obrigatoria'),
    ]

    operations = [
        migrations.RunPython(renomeia_duplicadas, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='sala',
            constraint=models.UniqueConstraint(
                fields=('organizacao', 'nome'), name='sala_nome_unico_por_org'
            ),
        ),
    ]
