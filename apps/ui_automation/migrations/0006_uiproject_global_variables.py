from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0005_testcasestep_save_as'),
    ]

    operations = [
        migrations.AddField(
            model_name='uiproject',
            name='global_variables',
            field=models.JSONField(blank=True, default=list, verbose_name='项目全局变量'),
        ),
    ]
