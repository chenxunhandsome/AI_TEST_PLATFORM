from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0014_testcasestep_transaction_disabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcasestep',
            name='element_locator_strategy',
            field=models.CharField(blank=True, max_length=50, verbose_name='步骤级定位策略'),
        ),
        migrations.AddField(
            model_name='testcasestep',
            name='element_locator_value',
            field=models.TextField(blank=True, verbose_name='步骤级定位表达式'),
        ),
    ]
