from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0006_uiproject_global_variables'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcasestep',
            name='transaction_id',
            field=models.CharField(blank=True, db_index=True, max_length=64, verbose_name='事务块ID'),
        ),
        migrations.AddField(
            model_name='testcasestep',
            name='transaction_name',
            field=models.CharField(blank=True, max_length=100, verbose_name='事务块名称'),
        ),
    ]
