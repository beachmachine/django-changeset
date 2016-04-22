================
Django ChangeSet
================

Django ChangeSet is a simple Django app that will give your models the possibility to track all changes. It depends on
"django_userforeignkey" to determine the users doing the changes. It is compatible with Django 1.8 and 1.9, and runs
with both, Python 2.7+ and 3.4+.

Getting Started
---------------

1. Use ``pip`` to install and download django-changeset (will automatically resolve the dependency on
``django_userforeignkey``):

.. code-block:: bash

    pip install git+https://github.com/beachmachine/django-changeset.git


2. Add ``django_userforeignkey`` and ``django_changeset`` to your INSTALLED_APPS setting like this:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'django_userforeignkey',
        'django_changeset',
    ]


3. Add ``django_userforeignkey.middleware.UserForeignKeyMiddleware`` to your MIDDLEWARE_CLASSES settings like this:

.. code-block:: python

    MIDDLEWARE_CLASSES = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        ...
        'django_userforeignkey.middleware.UserForeignKeyMiddleware',
    )


  Make sure to insert the ``django_userforeignkey`` middleware **after** the authentication middleware.


4. In your models, you need to use ``RevisionModelMixin`` as a mixin class all models that you want to track. This will do two things:

  - Your object will be tracked based on the config defined in the meta class (using ``track_by``, ``track_fields`` and ``track_related``)
  - Your object will be extended with properties that allow you to access the changeset/revisions (e.g., ``change_sets``, ``created_by``, ``created_at``, ...)


Configuration
-------------
By using the attributes ``track_by``, ``track_fields`` and ``track_related`` you can define which attributes of your
model should be tracked.

* ``track_by`` is an optional field which you should use when you specify which allows you to specify which field
  should be used as the primary key
* ``track_fields`` is a required field. By providing a list you can specify which fields should be tracked.
* ``track_related`` is an optional field for tracking changes on related models, by providing a list of related fields.

*Example 1 (without specifying primary key):*

.. code-block:: python

    from django.db import models
    from django_changeset.models import RevisionModelMixin

    class MyModel(models.Model, RevisionModelMixin):
        class Meta:
            track_fields = ('my_data', )
            track_related = ('my_ref', )

        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')


*Example 2 (specifying primary key):*

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



**NOTE**: Do **not** use any of the following names in your models: ``created_at``, ``created_by``, ``change_sets``,
``last_modified_by``, ``last_modified_at``, ``changed_data``


Properties
----------

By using ``RevisionModelMixin``, the following properties have been added to your model:

* ``created_at``: Gets the date when this object was created (django.db.models.DateTimeField)
* ``created_by``: Gets the user that created this object (django.contrib.auth.models.User)
* ``last_modified_at``: Gets the date when the object was last modified (django.db.models.DateTimeField)
* ``last_modified_by``: Gets the user that last modified the object (django.contrib.auth.models.User)
* ``changed_data``: A dictionary containing the names of changed fields as keys, and the original and new value as a list
* ``change_sets``: A list of changesets, which you can iterate over (see below)


Accessing the Changeset of a Model
----------------------------------

You can access the changeset of a model simply by calling the "change_set" property of an instance of "MyModel" as shown in the
following example:

.. code-block:: python

    print("------- CHANGE SETS (", len(MyModel.change_sets), ")---------")
    for change_set in MyModel.change_sets:
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



Accessing the Changeset of a User (all changes that the user ever did)
----------------------------------------------------------------------

.. code-block:: python

    print("------- CHANGE SETS OF USER (", len(someuser.all_changes), ")---------")
    for change_set in someuser.all_changess:
        # print change_set
        print("Change was carried out at ", change_set.date, " by user ", change_set.user, " on model ", change_set.object_type)
        # ... see above


Using filters `created_by`, `updated_by`, `deleted_by`
------------------------------------------------------

We implemented a mixin for Djangos ``QuerySet``, which allows you to query objects like this:


.. code-block:: python

    MyModel.objects.created_by_current_user()
    MyModel.objects.updated_by_current_user()


Internally, this is nothing other than a subquery over the ``ChangeSet`` model and the current ``MyModel``. To use this,
you need to add a custom queryset and a custom manager, like shown below.


.. code-block:: python

    from django_changeset.models.querysets import ChangeSetQuerySetMixin
    from django.db.models import QuerySet

    class MyModelQuerySet(QuerySet, ChangeSetQuerySetMixin):
        pass

    class MyModel:
        ...
        objects = models.Manager.from_queryset(MyModelQuerySet)()



Defining a 'foreign-key' like element
-------------------------------------

Usually you would have something like this in your model:


.. code-block:: python

    class MyModel(models.Model):
        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        created_by = ForeignKey(User, related_name='models')


This would allow you to access the models of a certain user by using the ``related_name`` property, in this case by
calling ``myuser.models``. To accomplish the same with the changeset, we added a meta-property called
``related_name_user``, as shown in the example below:


.. code-block:: python

    import uuid

    from django.db import models
    from django_changeset.models import RevisionModelMixin

    class MyModel(models.Model, RevisionModelMixin):
        class Meta:
            track_by = 'my_pk'
            track_fields = ('my_data', )
            track_related = ('my_ref', )
            related_name_user = 'models'

        my_pk = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')


This now allows you to access all models of a user by calling ``myuser.get_models()``. The method returns a list of
objects (in this case MyModel). Please bear in mind that the method always starts with a "get_", regardless of what
you specify in ``related_name_user``.