================
Django ChangeSet
================

Django ChangeSet is a simple Django app that will give your models the possibility to track all changes. It depends on
``django_userforeignkey`` to determine the current user doing the change(s).

Currently, Django 2.2 and 3.0 are supported.

Getting Started
---------------

1. Use ``pip`` to install and download django-changeset (and ``django-userforeignkey``):

.. code-block:: bash

    pip install django-changeset


2. Add ``django_userforeignkey`` and ``django_changeset`` to your ``INSTALLED_APPS`` like this:

.. code-block:: python

    INSTALLED_APPS = [
        ...
        'django_userforeignkey',
        'django_changeset',
    ]


3. Add ``django_userforeignkey.middleware.UserForeignKeyMiddleware`` to your ``MIDDLEWARE`` like this:

.. code-block:: python

    MIDDLEWARE = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        ...
        'django_userforeignkey.middleware.UserForeignKeyMiddleware',
    )


**Note**: Make sure to insert the ``django_userforeignkey`` middleware **after** the authentication middleware.


Example Usage 1: Track a model with a UUID as Primary Key
---------------------------------------------------------

1. Create a new Base Model Class like this:

.. code:: python

    from django.db import models

    class BaseModel(models.Model):
        """
        BaseModel is needed for proper MRO within Python/Django Models
        """
        class Meta:
            abstract = True
        pass


2. Make sure your models inherit from your ``BaseModel``, ``CreatedModifiedByMixin`` and ``RevisionModelMixin`` (the order here is important for Python to perform proper MRO resolution):

.. code:: python

    from django_changeset.models import CreatedModifiedByMixin, RevisionModelMixin

    class Poll(BaseModel, CreatedModifiedByMixin, RevisionModelMixin):
        class Meta:
            track_fields = ('question', 'pub_date',)

        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

        question = models.CharField(max_length=200)
        pub_date = models.DateTimeField(verbose_name="Publication date of poll")

        def __str__(self):
            return self.question


3. For bonus features, add a generic relation to the ``ChangeSet`` model and a ``version_number`` field:

.. code:: python

    class Poll(BaseModel, CreatedModifiedByMixin, RevisionModelMixin):
        class Meta:
            track_fields = ('question', 'pub_date',)

        # ...

        # add relation to changeset using object_uuid, as our primary key is a UUIDField
        changesets = ChangeSetRelation(
            object_id_field='object_uuid'
        )

        # define a version field that automatically increases on every change of the model
        version_number = ChangesetVersionField()


Example Usage 2: Minimum example
--------------------------------

2. Make sure your models inherit from your ``models.Model`` and ``RevisionModelMixin``:

.. code:: python

    from django_changeset.models import RevisionModelMixin

    class Poll(models.Model, RevisionModelMixin):
        class Meta:
            track_fields = ('question', 'pub_date',)

        question = models.CharField(max_length=200)
        pub_date = models.DateTimeField(verbose_name="Publication date of poll")

        def __str__(self):
            return self.question


3. For bonus features, add a generic relation to the ``ChangeSet`` model:

.. code:: python

    class Poll(models.Model, RevisionModelMixin):
        class Meta:
            track_fields = ('question', 'pub_date',)

        # ...

        # add relation to changeset using object_uuid, as our primary key is a UUIDField
        changesets = ChangeSetRelation()



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

    class MyModel(BaseModelWithChangeSet, RevisionModelMixin):
        class Meta:
            track_by = 'my_pk'
            track_fields = ('my_data', )
            track_related = ('my_ref', )

        my_pk = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')


In addition, the following attributes can be used to customize the behaviour:

- ``aggregate_changesets_within_seconds`` (default: `0`)
  If another changeset is created within the specified time by the same user, the changesets are merged/aggregated. Can be deactivated by setting to 0.

- ``track_soft_delete_by`` (default: `None`)
  Allows tracking soft deletes


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

    class MyModel(models.Model, RevisionModelMixin, CreatedModifiedByMixin):
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

    class MyModel(models.Model, RevisionModelMixin, CreatedModifiedByMixin):
        class Meta:
            track_fields = ('....', 'deleted',)  # Make sure to include the `deleted` field in `track_fields`
            track_soft_delete_by = 'deleted'

        # your model definition ...

        deleted = models.BooleanField(default=False, verbose_name="Whether this object is soft deleted or not")

        ...

        changesets = ChangeSetRelation()


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
objects (in this case MyModel). Please bear in mind that the method always starts with a `get_`, regardless of what
you specify in ``related_name_user``.