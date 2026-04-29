from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('submission', '0001_initial'),
        ('vae_workflow', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArticlePoolAvailability',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('available', models.BooleanField(default=False)),
                ('date_made_available', models.DateTimeField(blank=True, null=True)),
                ('article', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pool_availability',
                    to='submission.article',
                )),
                ('made_available_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pool_availabilities_made',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
