from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0007_testcasestep_transaction_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcasestep',
            name='is_enabled',
            field=models.BooleanField(default=True, verbose_name='是否启用'),
        ),
    ]
