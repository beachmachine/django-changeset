Django ChangeSet
================

[![Linter and tests](https://github.com/beachmachine/django-changeset/workflows/Linter%20and%20tests/badge.svg)](https://github.com/beachmachine/django-changeset/actions)
[![Codecov](https://img.shields.io/codecov/c/gh/beachmachine/django-changeset)](https://codecov.io/gh/beachmachine/django-changeset)

Django ChangeSet is a simple Django app that will give your models the possibility to track all changes. It depends on
`django_userforeignkey` to determine the current user doing the change(s).

Currently, Django 2.2 and 3.0 are supported and tested via GitHub Actions.

Detailed documentation is in the docs subdirectory.

Quick start
-----------

1.  Use `pip` to install and download django-changeset (and `django-userforeignkey`):

```bash
pip install django-changeset
```

2.  Add `django_userforeignkey` and `django_changeset` to your `INSTALLED_APPS` like this:

```python
INSTALLED_APPS = [
    ...
    'django_userforeignkey',
    'django_changeset',
]
```

3.  Add `django_userforeignkey.middleware.UserForeignKeyMiddleware` to your `MIDDLEWARE` like this:

```python
MIDDLEWARE = (
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    ...
    'django_userforeignkey.middleware.UserForeignKeyMiddleware',
)
```

**Note**: Make sure to insert the `UserForeignKeyMiddleware` **after** Djangos `AuthenticationMiddleware`.

Example usage
-------------

***Use `RevisionModelMixin` as a mixin class for your models and add the fields you want to track in the meta***
configuration using `track_fields` and `track_related`. Also add a generic relation to `ChangeSet` using
`changesets = ChangeSetRelation()`:

```python
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
```

Note: If you want to have access to the properties `created_by`, `created_at`, `last_modified_by`, `last_modified_at`,
you need to inherit from `CreatedModifiedByMixin` aswell as `RevisionModelMixin`. For the Python MRO to work, you also
have to create an abstract base model:

```python
from django.db import models

from django_changeset.models import CreatedModifiedByMixin, RevisionModelMixin
from django_changeset.models.fields import ChangeSetRelation



class BaseModel(models.Model):
    """
    BaseModel is needed for proper MRO within Python/Django Models
    """
    class Meta:
        abstract = True
    pass


class MyModel(BaseModel, RevisionModelMixin, CreatedModifiedByMixin):
    class Meta:
        track_fields = ('my_data', )  # track changes on my_data
        track_related = ('my_ref', )  # track changes on a related model

    my_data = models.CharField(max_length=64, verbose_name="Very important data you want to track")
    my_ref = models.ForeignKey('SomeOtherModel', verbose_name="Very important relation", related_name='my_models')

    # Generic Relation to ChangeSet
    changesets = ChangeSetRelation()
```

Querying ChangeSets via the changesets relation
-----------------------------------------------

By inheriting from the `RevisionModelMixin` and `CreatedModifiedByMixin` mixins, and adding an attribute of type
`ChangeSetRelation` (a `GenericRelation` for the changeset), the following features are added to your model:

-   Properties `created_by`, `created_at`, `last_modified_by`, `last_modified_at` are made available for each object
    (`CreatedModifiedByMixin`)
-   Relation `changesets` is made available, allowing you to run queries like this one:
    `MyModel.objects.filter(changesets__changeset_type='I', changesets__user__username='johndoe')`

Access ChangeSets and ChangeRecords
-----------------------------------

ToDo

You can access the changeset by calling the `change_set` property of an instance of `MyModel` as shown in the following
example:

```python
print("------- CHANGE SETS (", len(somemodel.changesets), ")---------")
for change_set in somemodel.changesets:
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
```

Maintainers
-----------

This repository is currently maintained by

-   beachmachine
-   anx-mpoelzl

Pull Requests are welcome.

License
-------

Django ChangeSet uses the BSD-3 Clause License, see LICENSE file.
