from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ui_automation', '0018_testcasestep_get_attribute'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcaseexecution',
            name='step_details',
            field=models.JSONField(blank=True, default=list, verbose_name='步骤详情'),
        ),
        migrations.CreateModel(
            name='UiExecutionCleanupSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False, verbose_name='是否启用')),
                ('retention_days', models.PositiveIntegerField(default=30, verbose_name='保留天数')),
                ('last_cleaned_at', models.DateTimeField(blank=True, null=True, verbose_name='最后清理时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ui_execution_cleanup_settings', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='execution_cleanup_setting', to='ui_automation.uiproject', verbose_name='所属项目')),
            ],
            options={
                'verbose_name': 'UI执行记录清理配置',
                'verbose_name_plural': 'UI执行记录清理配置',
                'db_table': 'ui_execution_cleanup_settings',
                'ordering': ['project_id'],
            },
        ),
    ]
