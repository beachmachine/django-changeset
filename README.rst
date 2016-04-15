================
Django ChangeSet
================

Django ChangeSet is a simple Django app that will give your models the possibility to track all changes. It depends on
"django_userforeignkey" to determine the users doing the changes.

Quick start
-----------

1. Add "django_userforeignkey" and "django_changeset" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'django_userforeignkey',
        'django_changeset',
    ]

2. Add "django_userforeignkey.middleware.UserForeignKeyMiddleware" to your MIDDLEWARE_CLASSES settings like this::

    MIDDLEWARE_CLASSES = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        ...
        'django_userforeignkey.middleware.UserForeignKeyMiddleware',
    )

  Make sure to insert the "django_userforeignkey" middleware after the authentication middleware.

Example usage
-------------

Use "RevisionModelMixin" as a mixin class for your models and add the fields you want to track in the meta
configuration::

    import uuid

    from django.db import models
    from django_changeset.models import RevisionModelMixin

    class MyModel(models.Model, RevisionModelMixin):
        class Meta:
            track_by = 'my_pk'
            track_fields = ('my_data', )
            track_related = {
                'my_ref': 'my_models',
            }

        my_pk = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
        my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
        my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')
