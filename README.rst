================
Django ChangeSet
================

.. image:: https://travis-ci.org/beachmachine/django-changeset.svg?branch=master
    :target: https://travis-ci.org/beachmachine/django-changeset

Django ChangeSet is a simple Django app that will give your models the possibility to track all changes. It depends on
"django_userforeignkey" to determine the users doing the changes. It is compatible with Django 1.8 and 1.9, and runs
with both, Python 2.7+ and 3.4+.

Quick start
-----------

1. Add "django_userforeignkey" and "django_changeset" to your INSTALLED_APPS setting like this:

.. code-block:: python
    INSTALLED_APPS = [
        ...
        'django_userforeignkey',
        'django_changeset',
    ]

2. Add "django_userforeignkey.middleware.UserForeignKeyMiddleware" to your MIDDLEWARE_CLASSES settings like this:

.. code-block:: python
    MIDDLEWARE_CLASSES = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        ...
        'django_userforeignkey.middleware.UserForeignKeyMiddleware',
    )

  Make sure to insert the "django_userforeignkey" middleware after the authentication middleware.

Example usage
-------------

Use "RevisionModelMixin" as a mixin class for your models and add the fields you want to track in the meta configuration:

.. code-block:: python
    import uuid

    from django.db import models
    from django_changeset.models import RevisionModelMixin

    class MyModel(models.Model, RevisionModelMixin):
        class Meta:
            track_by = 'my_pk'
            track_fields = ('my_data', )
            track_related = {
                'my_ref': 'my_models', # where 'my_ref' is the local attribute name, and 'my_models' is the related name (see below)
            }

        my_pk = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')


You can access the changeset by calling the "change_set" property of an instance of "MyModel" as shown in the following example:

.. code-block:: python
    print("------- CHANGE SETS (", len(somemodel.change_sets), ")---------")
    for change_set in somemodel.change_sets):
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

Do **not** use any of the following names in your models: "created_at", "created_by", "change_sets", "last_modified_by", "last_modified_at", "changed_data"

