from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0013_aitestcasegenerationskillcategory_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcasestep',
            name='transaction_disabled',
            field=models.BooleanField(default=False, verbose_name='事务块是否禁用'),
        ),
    ]
