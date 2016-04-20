# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_userforeignkey.models.fields
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChangeRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('field_name', models.CharField(verbose_name='Field name', max_length=255, editable=False)),
                ('old_value', models.TextField(verbose_name='Old value', null=True, editable=False, blank=True)),
                ('new_value', models.TextField(verbose_name='New value', null=True, editable=False, blank=True)),
                ('is_related', models.BooleanField(default=False, verbose_name='Is change on related entity', editable=False)),
            ],
            options={
                'ordering': ['-change_set__date', 'field_name'],
                'get_latest_by': 'change_set__date',
            },
        ),
        migrations.CreateModel(
            name='ChangeSet',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('changeset_type', models.CharField(default=b'I', verbose_name='Changeset Type', max_length=1, editable=False, choices=[(b'I', b'Insert'), (b'U', b'Update'), (b'D', b'Delete')])),
                ('date', models.DateTimeField(auto_now_add=True, verbose_name='Date')),
                ('object_uuid', models.CharField(verbose_name='Object UUID', max_length=255, editable=False)),
                ('object_type', models.ForeignKey(editable=False, to='contenttypes.ContentType', verbose_name='Object type')),
                ('user', django_userforeignkey.models.fields.UserForeignKey(related_name='all_changes', on_delete=django.db.models.deletion.SET_NULL, verbose_name='User', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ['-date'],
                'get_latest_by': 'date',
            },
        ),
        migrations.AddField(
            model_name='changerecord',
            name='change_set',
            field=models.ForeignKey(related_name='change_records', editable=False, to='django_changeset.ChangeSet'),
        ),
    ]
