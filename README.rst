================
Django ChangeSet
================

.. image:: https://travis-ci.org/beachmachine/django-changeset.svg?branch=master
    :target: https://travis-ci.org/beachmachine/django-changeset

Django ChangeSet is a simple Django app that will give your models the possibility to track all changes. It depends on
``django_userforeignkey`` to determine the users doing the changes. 

Currently, Django 1.8 (Python 2.7, Python 3.3+), Django 1.9 (Python 2.7, Python 3.4+) and Django 1.10 (Python 2.7, Python 3.5+) are supported.

Detailed documentation is in the docs subdirectory (see :file:`./docs/index.rst`).

Quick start
-----------

1. Use ``pip`` to install and download django-changeset (will automatically resolve the dependency on
django_userforeignkey):

.. code-block:: bash

    pip install django-userforeignkey
    pip install git+https://github.com/beachmachine/django-changeset.git


2. Add ``django_userforeignkey`` and ``django_changeset`` to your INSTALLED_APPS setting like this:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'django_userforeignkey',
        'django_changeset',
    ]


3. Add ``django_userforeignkey.middleware.UserForeignKeyMiddleware`` to your ``MIDDLEWARE_CLASSES`` (Django 1.10 ``MIDDLEWARE`` also works) settings like this:

.. code-block:: python

    MIDDLEWARE_CLASSES = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        ...
        'django_userforeignkey.middleware.UserForeignKeyMiddleware',
    )



Make sure to insert the ``django_userforeignkey`` middleware **after** the authentication middleware.


Example usage
-------------

Use ``RevisionModelMixin`` as a mixin class for your models and add the fields you want to track in the meta configuration:

.. code-block:: python

    import uuid

    from django.db import models
    from django_changeset.models import RevisionModelMixin

    class MyModel(models.Model, RevisionModelMixin):
        class Meta:
            track_by = 'my_pk'
            track_fields = ('my_data', )
            track_related = ('my_ref', )

        my_pk = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')


You can access the changeset by calling the ``change_set`` property of an instance of ``MyModel`` as shown in the
following example:

.. code-block:: python

    print("------- CHANGE SETS (", len(somemodel.change_sets), ")---------")
    for change_set in somemodel.change_sets:
        # print change_set
        print("Change was carried out at ", change_set.date, " by user ", change_set.user, " on model ", change_set.object_type)

        print("  + CHANGE RECORDS (", len(change_set.change_records.all()), "): ")
        for change_record in change_set.change_records.all():
            print("\t", change_record)
            print("\tIs change on a related field?", change_record.is_related)
            # related fields: we only know that something new has been added. we know the PK, but not the object itself
            print("\t\tChanged field ", change_record.field_name, "(", change_record.field_verbose_name, ") from ",
                  change_record.old_value, "(display:", change_record.old_value_display, ") to")
            print("\t\t ", change_record.new_value, "(display:", change_record.new_value_display, ")")
            if change_record.is_related:
                print("\t\tRelated Object Info: ", change_record.related_object)
        # TODO:
        # change_set.created_at, change_set.created_by, change_set.last_modified_by, change_set.last_modified_at

        print("-----")


Known problems
--------------

Do **not** use any of the following names in your models: ``created_at``, ``created_by``, ``change_sets``,
``last_modified_by``, ``last_modified_at``, ``changed_data``


Generic Relations
-----------------

It is possible to use Django Changeset with Djangos ``GenericRelation`` like this (tested with Django 1.11):

.. code-block:: python

    class MyModel(models.Model, RevisionModelMixin):
        ...

        changesets = GenericRelation(
            ChangeSet,
            content_type_field='object_type',
            object_id_field='object_uuid'
        )


This allows the Django ORM to use queries on changeset (e.g., on the changeset type INSERT):

.. code-block:: python

    MyModel.objects.filter(changesets__changeset_type='I')



Generic Relations with UUID
---------------------------

The query from above does not work in Postgres when using the built-in ``UUID`` datatype, e.g.:

.. code-block:: python

    class MyModel(models.Model, RevisionModelMixin):
        my_pk = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)

        ...

        changesets = GenericRelation(
            ChangeSet,
            content_type_field='object_type',
            object_id_field='object_uuid'
        )


This is due to the fact that the ``ChangeSet`` model uses a ``CharField(max_length=...)`` for the ``object_uuid``.
It is possible to change this behaviour by using ``DJANGO_CHANGESET_PK_TYPE = "UUID"`` in your Django settings file.
This will convert swap out the basic ``object_uuid`` field from:

.. code-block:: python

    object_uuid = models.CharField(
        verbose_name=_(u"Object UUID"),
        max_length=255,
        editable=False,
    )

to this:

.. code-block:: python

    object_uuid = models.UUIDField(
        verbose_name=_(u"Object UUID"),
        editable=False,
    )


This obviously **requires** a migration! Do **not** run the ``makemigrations`` command to do this. Instead, add a
migration file manually to **your application** (e.g., ``your_app``), which will look something like this:

.. code-block:: python

    # -*- coding: utf-8 -*-
    # Generated by Django 1.11.2 on 2017-06-30 08:22
    from __future__ import unicode_literals

    from django.db import migrations, models


    class Migration(migrations.Migration):
        dependencies = [
            ('django_changeset', '0002_add_index_changesettype'),
            ('your_app', '0815_your_last_migration')
        ]

        operations = [
            migrations.AlterField(
                model_name='changeset',
                name='object_uuid',
                field=models.UUIDField(editable=False, verbose_name='Object UUID'),
            ),
        ]

        def __init__(self, name, app_label):
            super(Migration, self).__init__(name, 'django_changeset')


