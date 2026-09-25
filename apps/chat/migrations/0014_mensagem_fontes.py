from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('chat', '0013_conversa_visitada_em')]

    operations = [
        migrations.AddField(
            model_name='mensagem',
            name='fontes',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
