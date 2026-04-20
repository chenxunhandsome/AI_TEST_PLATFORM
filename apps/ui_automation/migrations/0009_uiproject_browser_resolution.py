from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0008_testcasestep_is_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='uiproject',
            name='browser_height',
            field=models.PositiveIntegerField(default=1060, verbose_name='浏览器高度'),
        ),
        migrations.AddField(
            model_name='uiproject',
            name='browser_width',
            field=models.PositiveIntegerField(default=1920, verbose_name='浏览器宽度'),
        ),
    ]
