================
Django ChangeSet
================

Work in Progress - a new version is coming out soon(TM)

.. image:: https://travis-ci.org/beachmachine/django-changeset.svg?branch=master
    :target: https://travis-ci.org/beachmachine/django-changeset

Django ChangeSet is a simple Django app that will give your models the possibility to track all changes. It depends on
``django_userforeignkey`` to determine the current user doing the change(s).

Currently, Django 1.11, 2.0 and 2.1 are supported.

Detailed documentation is in the docs subdirectory (see :file:`./docs/index.rst`).

Quick start
-----------

1. Use ``pip`` to install and download django-changeset (and ``django-userforeignkey``):

.. code-block:: bash

    pip install django-changeset


2. Add ``django_userforeignkey`` and ``django_changeset`` to your ``INSTALLED_APPS`` setting like this:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'django_userforeignkey',
        'django_changeset',
    ]


3. Add ``django_userforeignkey.middleware.UserForeignKeyMiddleware`` to your ``MIDDLEWARE`` settings like this:

.. code-block:: python

    MIDDLEWARE = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        ...
        'django_userforeignkey.middleware.UserForeignKeyMiddleware',
    )



**Note**: Make sure to insert the ``UserForeignKeyMiddleware`` **after** Djangos ``AuthenticationMiddleware``.


Example usage
-------------

Use ``RevisionModelMixin`` as a mixin class for your models and add the fields you want to track in the meta
 configuration using ``track_fields`` and ``track_related``. Also add a generic relation to ``ChangeSet`` using ``changesets = ChangeSetRelation()``:

.. code-block:: python

    from django.db import models

    from django_changeset.models import RevisionModelMixin
    from django_changeset.models.fields import ChangeSetRelation


    class MyModel(models.Model, RevisionModelMixin):
        class Meta:
            track_fields = ('my_data', )  # track changes on my_data
            track_related = ('my_ref', )  # track changes on a related model

        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')

        # Generic Relation to ChangeSet
        changesets = ChangeSetRelation()


Note: If you want to have access to the properties ``created_by``, ``created_at``, ``last_modified_by``, ``last_modified_at``,
you need to inherit from ``CreatedModifiedByMixIn`` aswell as ``RevisionModelMixin``:

.. code-block:: python

    from django.db import models

    from django_changeset.models import RevisionModelMixin
    from django_changeset.models.fields import ChangeSetRelation


    class MyModel(models.Model, RevisionModelMixin, CreatedModifiedByMixIn):
        class Meta:
            track_fields = ('my_data', )  # track changes on my_data
            track_related = ('my_ref', )  # track changes on a related model

        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')

        # Generic Relation to ChangeSet
        changesets = ChangeSetRelation()


Querying ChangeSets via the changesets relation
-----------------------------------------------

By inheriting from the ``RevisionModelMixin`` and ``CreatedModifiedByMixIn`` mixins, and adding an attribute of type ``ChangeSetRelation`` (a ``GenericRelation`` for the changeset), the following features are added to your model:

- Properties ``created_by``, ``created_at``, ``last_modified_by``, ``last_modified_at`` are made available for each object (``CreatedModifiedByMixIn``)
- Relation ``changesets`` is made available, allowing you to run queries like this one:
 ``MyModel.objects.filter(changesets__changeset_type='I', changesets__user__username='johndoe')``


Using ChangeSet with UUIDFields as Primary Key
----------------------------------------------

If your models use UUIDFields as a primary key, you just need to add a parameter to ``ChangeSetRelation``: ``object_id_field='object_uuid'``

Please note that ``object_uuid`` is the name of an indexed ``UUIDField`` on the ``ChangeSet`` model.

.. code-block:: python

    import uuid

    from django.db import models

    from django_changeset.models import RevisionModelMixin, CreatedModifiedByMixIn
    from django_changeset.models.fields import ChangeSetRelation

    class MyModelWithUuid(models.Model, RevisionModelMixin, CreatedModifiedByMixIn):
        class Meta:
            track_fields = ('my_data', )
            track_related = ('my_ref', )

        id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')

        # Generic Relation to ChangeSet
        changesets = ChangeSetRelation(
            object_id_field='object_uuid'
        )



Performance Improvement when querying ChangeSets: Select Related User and User Profile
--------------------------------------------------------------------------------------

Whenever you query/filter on the ChangeSets, you will most likely want to include information about the user. Therefore we modified the default
behaviour of the ChangeSet QuerySet Manager to automatically join the ChangeSet table via the user foreign key. 

.. code-block:: python

    class ChangeSetManager(models.Manager):
    """
    ChangeSet Manager that forces all ChangeSet queries to contain at least the "user" foreign relation
    """
    def get_queryset(self):
        return super(ChangeSetManager, self).get_queryset().select_related(
            "user"
        )


This can furthermore be configured with the setting ``DJANGO_CHANGESET_SELECT_RELATED``, e.g. if you not only want to join this with information 
 from the user table, but also information from the userprofile table:

.. code-block:: python

    DJANGO_CHANGESET_SELECT_RELATED=["user", "user__userprofile"]


If you want to disable this feature, just set ``DJANGO_CHANGESET_SELECT_RELATED=[]``.


Automatically Aggregate Changesets and Changerecords
----------------------------------------------------

Django Changeset can automatically aggregate changests and changerecords, if they are created by the same user within
a given timedelta. This is very useful if you are doing partial updates of your model (e.g., PATCH requests in a REST
API).

You can configure this by setting ``aggregate_changesets_within_seconds`` in the models meta class, e.g.:

.. code-block:: python

    class MyModel(models.Model, RevisionModelMixin, CreatedModifiedByMixIn):
        class Meta:
            aggregate_changesets_within_seconds = 60  # aggregate changesets created by the same user within 60 seconds

        # your model definition ...

        changesets = ChangeSetRelation()


Soft Delete and Restore Functionality
-------------------------------------

Django Changeset supports soft-deleting aswell as restoring an object. Those actions will
be marked with changeset type ``R`` (``ChangeSet.RESTORE_TYPE``) for restore, and ``S`` (``ChangeSet.SOFT_DELETE_TYPE``) for soft delete.


You can enable tracking soft deletes and restores by setting ``track_soft_delete_by`` aswell as ``track_fields`` accordingly in the models meta class, e.g.:

.. code-block:: python

    class MyModel(models.Model, RevisionModelMixin, CreatedModifiedByMixIn):
        class Meta:
            track_fields = ('....', 'deleted',)  # Make sure to include the `deleted` field in `track_fields`
            track_soft_delete_by = 'deleted'

        # your model definition ...
        
        deleted = models.BooleanField(default=False, verbose_name="Whether this object is soft deleted or not")

        ...

        changesets = ChangeSetRelation()


Access ChangeSets and ChangeRecords
-----------------------------------

ToDo

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


Maintainers
-----------
This repository is currently maintained by

- beachmachine
- ChristianKreuzberger

Pull Requests are welcome.

License
-------

Django ChangeSet uses the BSD-3 Clause License, see LICENSE file.


Changelog / Release History
---------------------------

Work in progress - No official release yet
