from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0015_testcasestep_element_locator_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcaseexecution',
            name='execution_plan',
            field=models.JSONField(blank=True, default=dict, verbose_name='执行步骤计划'),
        ),
    ]
