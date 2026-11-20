from django.db import migrations, models


def perfis_existentes_viram_administrador(apps, schema_editor):
    # Quem já usava o sistema continua podendo tudo
    Perfil = apps.get_model('core', 'Perfil')
    Perfil.objects.update(papel='administrador')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfil',
            name='papel',
            field=models.CharField(
                choices=[
                    ('administrador', 'Administrador'),
                    ('operador', 'Operador'),
                    ('usuario', 'Usuário'),
                ],
                default='usuario',
                max_length=20,
            ),
        ),
        migrations.RunPython(perfis_existentes_viram_administrador, migrations.RunPython.noop),
    ]
