from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0004_testcasefolder_testcase_folder_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcasestep',
            name='save_as',
            field=models.CharField(blank=True, max_length=100, verbose_name='Stored Variable Name'),
        ),
    ]
