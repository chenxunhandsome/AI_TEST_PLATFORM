from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0022_ui_page_graph'),
    ]

    operations = [
        migrations.AddField(
            model_name='uipagegraph',
            name='progress',
            field=models.JSONField(blank=True, default=dict, verbose_name='Crawl Progress'),
        ),
        migrations.AddField(
            model_name='uipagegraph',
            name='crawl_state',
            field=models.JSONField(blank=True, default=dict, verbose_name='Crawl State'),
        ),
        migrations.AddField(
            model_name='uipagegraph',
            name='heartbeat_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Heartbeat At'),
        ),
        migrations.AlterField(
            model_name='uipagegraph',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('running', 'Running'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('timeout', 'Timeout'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
                verbose_name='Status',
            ),
        ),
    ]
