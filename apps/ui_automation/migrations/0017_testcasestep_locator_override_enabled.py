from django.db import migrations, models


def mark_existing_step_locator_overrides(apps, schema_editor):
    TestCaseStep = apps.get_model('ui_automation', 'TestCaseStep')
    TestCaseStep.objects.exclude(element_locator_value='').update(
        element_locator_override_enabled=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0016_testcaseexecution_execution_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcasestep',
            name='element_locator_override_enabled',
            field=models.BooleanField(default=False, verbose_name='是否启用步骤级定位覆盖'),
        ),
        migrations.RunPython(mark_existing_step_locator_overrides, migrations.RunPython.noop),
    ]
