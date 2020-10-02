# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-15 19:07
from __future__ import unicode_literals

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.timezone import utc
import django_userforeignkey.models.fields


class Migration(migrations.Migration):

    replaces = [('polls', '0001_initial'), ('polls', '0002_auto_20160414_1310'), ('polls', '0003_auto_20160414_1332'), ('polls', '0004_actualvote'), ('polls', '0005_auto_20160414_1351'), ('polls', '0006_auto_20171015_1907')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Choice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('choice_text', models.CharField(max_length=200)),
                ('votes', models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Poll',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.CharField(max_length=200)),
                ('pub_date', models.DateTimeField(verbose_name=b'Publication date of poll')),
                ('created_by', django_userforeignkey.models.fields.UserForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='polls', to=settings.AUTH_USER_MODEL, verbose_name=b'The user that created the poll')),
                ('created_at', models.DateTimeField(auto_now_add=True, default=datetime.datetime(2016, 4, 14, 13, 32, 11, 409531, tzinfo=utc), verbose_name=b'Publication date of poll')),
            ],
        ),
        migrations.AddField(
            model_name='choice',
            name='poll',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='polls.Poll'),
        ),
        migrations.CreateModel(
            name='ActualVote',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('choice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='polls.Choice', verbose_name='Which choice was chosen?')),
                ('poll', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='polls.Poll', verbose_name='Which question has been voted for?')),
                ('user', django_userforeignkey.models.fields.UserForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='actual_votes', to=settings.AUTH_USER_MODEL, verbose_name='Which user has voted?')),
            ],
        ),
        migrations.AlterField(
            model_name='choice',
            name='poll',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='polls.Poll', verbose_name=b'Which poll?'),
        ),
        migrations.AlterField(
            model_name='choice',
            name='poll',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='polls.Poll', verbose_name='Which poll?'),
        ),
        migrations.AlterField(
            model_name='poll',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Publication date of poll'),
        ),
        migrations.AlterField(
            model_name='poll',
            name='created_by',
            field=django_userforeignkey.models.fields.UserForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='polls', to=settings.AUTH_USER_MODEL, verbose_name='The user that created the poll'),
        ),
        migrations.AlterField(
            model_name='poll',
            name='pub_date',
            field=models.DateTimeField(verbose_name='Publication date of poll'),
        ),
    ]
