from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('chat', '0014_mensagem_fontes')]

    operations = [
        migrations.AddField(
            model_name='mensagem',
            name='skill',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
