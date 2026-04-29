from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ui_automation', '0011_local_execution_for_suites_and_tasks'),
    ]

    operations = [
        migrations.CreateModel(
            name='AITestCaseGenerationSkill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Skill Name')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('content', models.TextField(verbose_name='Skill Content')),
                ('is_default', models.BooleanField(default=False, verbose_name='Default Skill')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_ui_ai_generation_skills', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
            ],
            options={
                'verbose_name': 'UI AI Test Case Generation Skill',
                'verbose_name_plural': 'UI AI Test Case Generation Skills',
                'db_table': 'ui_ai_test_case_generation_skills',
                'ordering': ['-is_default', '-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='AITestCaseGenerationRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ai_model_config_id', models.IntegerField(blank=True, null=True, verbose_name='AI Model Config ID')),
                ('source_type', models.CharField(choices=[('text', 'Text'), ('file', 'File'), ('mixed', 'Text And File')], default='text', max_length=20, verbose_name='Source Type')),
                ('source_name', models.CharField(blank=True, max_length=255, verbose_name='Source Name')),
                ('source_text', models.TextField(blank=True, verbose_name='Source Text')),
                ('manifest', models.JSONField(blank=True, default=dict, verbose_name='Generated Manifest')),
                ('warnings', models.JSONField(blank=True, default=list, verbose_name='Warnings')),
                ('status', models.CharField(choices=[('generated', 'Generated'), ('imported', 'Imported'), ('failed', 'Failed')], default='generated', max_length=20, verbose_name='Status')),
                ('import_summary', models.JSONField(blank=True, default=dict, verbose_name='Import Summary')),
                ('error_message', models.TextField(blank=True, verbose_name='Error Message')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ui_ai_test_case_generation_records', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_test_case_generation_records', to='ui_automation.uiproject', verbose_name='Project')),
                ('skill', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generation_records', to='ui_automation.aitestcasegenerationskill', verbose_name='Skill')),
            ],
            options={
                'verbose_name': 'UI AI Test Case Generation Record',
                'verbose_name_plural': 'UI AI Test Case Generation Records',
                'db_table': 'ui_ai_test_case_generation_records',
                'ordering': ['-created_at'],
            },
        ),
    ]
