from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ui_automation', '0021_testcasestep_parent_transaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='UIPageGraph',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Graph Name')),
                ('start_url', models.URLField(verbose_name='Start URL')),
                ('login_url', models.URLField(blank=True, verbose_name='Login URL')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], db_index=True, default='pending', max_length=20, verbose_name='Status')),
                ('crawl_config', models.JSONField(blank=True, default=dict, verbose_name='Crawl Config')),
                ('summary', models.JSONField(blank=True, default=dict, verbose_name='Summary')),
                ('error_message', models.TextField(blank=True, verbose_name='Error Message')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='Started At')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completed At')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_graphs', to='ui_automation.uiproject', verbose_name='Project')),
            ],
            options={
                'verbose_name': 'UI Page Graph',
                'verbose_name_plural': 'UI Page Graphs',
                'db_table': 'ui_page_graphs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UIPageNode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=1000, verbose_name='URL')),
                ('path', models.CharField(blank=True, max_length=500, verbose_name='Path')),
                ('title', models.CharField(blank=True, max_length=300, verbose_name='Title')),
                ('route_key', models.CharField(db_index=True, max_length=500, verbose_name='Route Key')),
                ('page_text', models.TextField(blank=True, verbose_name='Page Text')),
                ('keywords', models.JSONField(blank=True, default=list, verbose_name='Keywords')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Metadata')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('graph', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nodes', to='ui_automation.uipagegraph', verbose_name='Graph')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_graph_nodes', to='ui_automation.uiproject', verbose_name='Project')),
            ],
            options={
                'verbose_name': 'UI Page Graph Node',
                'verbose_name_plural': 'UI Page Graph Nodes',
                'db_table': 'ui_page_graph_nodes',
                'ordering': ['path', 'title'],
            },
        ),
        migrations.CreateModel(
            name='UIPageElement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=240, verbose_name='Name')),
                ('role', models.CharField(blank=True, max_length=80, verbose_name='Role')),
                ('element_type', models.CharField(default='BUTTON', max_length=50, verbose_name='Element Type')),
                ('text', models.CharField(blank=True, max_length=500, verbose_name='Text')),
                ('locator_strategy', models.CharField(max_length=50, verbose_name='Locator Strategy')),
                ('locator_value', models.TextField(verbose_name='Locator Value')),
                ('backup_locators', models.JSONField(blank=True, default=list, verbose_name='Backup Locators')),
                ('is_unique', models.BooleanField(default=False, verbose_name='Unique')),
                ('is_stable', models.BooleanField(default=False, verbose_name='Stable')),
                ('action_keywords', models.JSONField(blank=True, default=list, verbose_name='Action Keywords')),
                ('attributes', models.JSONField(blank=True, default=dict, verbose_name='Attributes')),
                ('bounds', models.JSONField(blank=True, default=dict, verbose_name='Bounds')),
                ('dom_signature', models.CharField(blank=True, db_index=True, max_length=128, verbose_name='DOM Signature')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('element', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='page_graph_links', to='ui_automation.element', verbose_name='Element')),
                ('graph', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='graph_elements', to='ui_automation.uipagegraph', verbose_name='Graph')),
                ('page_node', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements', to='ui_automation.uipagenode', verbose_name='Page Node')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_graph_elements', to='ui_automation.uiproject', verbose_name='Project')),
            ],
            options={
                'verbose_name': 'UI Page Graph Element',
                'verbose_name_plural': 'UI Page Graph Elements',
                'db_table': 'ui_page_graph_elements',
                'ordering': ['page_node', 'name'],
            },
        ),
        migrations.CreateModel(
            name='UIPageEdge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(default='click', max_length=50, verbose_name='Action Type')),
                ('trigger_text', models.CharField(blank=True, max_length=500, verbose_name='Trigger Text')),
                ('locator_strategy', models.CharField(blank=True, max_length=50, verbose_name='Locator Strategy')),
                ('locator_value', models.TextField(blank=True, verbose_name='Locator Value')),
                ('keywords', models.JSONField(blank=True, default=list, verbose_name='Keywords')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Metadata')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('graph', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='edges', to='ui_automation.uipagegraph', verbose_name='Graph')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_graph_edges', to='ui_automation.uiproject', verbose_name='Project')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_edges', to='ui_automation.uipagenode', verbose_name='Source')),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming_edges', to='ui_automation.uipagenode', verbose_name='Target')),
                ('trigger_element', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='triggered_edges', to='ui_automation.uipageelement', verbose_name='Trigger Element')),
            ],
            options={
                'verbose_name': 'UI Page Graph Edge',
                'verbose_name_plural': 'UI Page Graph Edges',
                'db_table': 'ui_page_graph_edges',
                'ordering': ['source', 'target', 'trigger_text'],
            },
        ),
        migrations.AddIndex(
            model_name='uipagegraph',
            index=models.Index(fields=['project', 'status'], name='ui_page_gr_project_e1de68_idx'),
        ),
        migrations.AddIndex(
            model_name='uipagegraph',
            index=models.Index(fields=['created_at'], name='ui_page_gr_created_e3ba86_idx'),
        ),
        migrations.AddConstraint(
            model_name='uipagenode',
            constraint=models.UniqueConstraint(fields=('graph', 'route_key'), name='ui_page_graph_node_unique_route'),
        ),
        migrations.AddIndex(
            model_name='uipagenode',
            index=models.Index(fields=['project', 'route_key'], name='ui_page_no_project_5bcd04_idx'),
        ),
        migrations.AddIndex(
            model_name='uipageelement',
            index=models.Index(fields=['project', 'element_type'], name='ui_page_el_project_24a5f8_idx'),
        ),
        migrations.AddIndex(
            model_name='uipageelement',
            index=models.Index(fields=['graph', 'is_unique'], name='ui_page_el_graph_i_0d870d_idx'),
        ),
        migrations.AddIndex(
            model_name='uipageedge',
            index=models.Index(fields=['project'], name='ui_page_ed_project_0f8ad3_idx'),
        ),
        migrations.AddIndex(
            model_name='uipageedge',
            index=models.Index(fields=['graph'], name='ui_page_ed_graph_i_2d40c2_idx'),
        ),
    ]
