from django_userforeignkey.request import get_current_user
from django.contrib.contenttypes.models import ContentType
from django_changeset.models import ChangeSet


def get_content_type_of(model):
    """
    Helper Method which gets the ContentType object (ContentType.objects.get_for_model(model)) for the given model
    :param model: the class/model
    :returns: the ContentType object of the model
    :rtype: django.contrib.contenttypes.models.ContentType
    """
    # if we are working on a deferred proxy class, we first need to get
    # the real model class, so we can save a new instance if we need.
    if getattr(model, '_deferred', False):
        model = model.__mro__[1]

    try:
        return ContentType.objects.get_for_model(model)
    except ContentType.DoesNotExist:
        return None


class ChangeSetQuerySetMixin(object):
    """ This is a mixin for QuerySets which is supposed to return a filter with all objects created, updated or (soft)
        deleted by the current user. The (soft) deleted option is only available if you also implemented (soft) delete
        (TODO).

        To extend an existing queryset with this mixin, use it as follows:

        from django_changeset.models.querysets import ChangeSetQuerySetMixin
        from django.db.models import QuerySet

        class MyModelQuerySet(QuerySet, ChangeSetQuerySetMixin):
            pass


        You also need to tell your model that you want to use the manager with this new queryset

        class MyModel:
            ...
            objects = models.Manager.from_queryset(MyModelQuerySet)()


        You can then use it as follows:

        qs_created = MyModel.objects.created_by_current_user()
        qs_updated = MyModel.objects.updated_by_current_user()
        qs_deleted = MyModel.objects.deleted_by_current_user() # this last one does not work yet (TODO)

    """

    def is_staff_or_created_by_current_user(self, *args, **kwargs):
        """
        returns all objects that have been created by the user (or if staff, all)
        """
        user = get_current_user()

        if user.is_staff:
            return self.all()
        else:
            return self.created_by_current_user(args, kwargs)

    def created_by_current_user(self, *args, **kwargs):
        """
        returns all objects that have been created by the user (based on the django changeset model)
        """
        user = get_current_user()

        return self.filter(created_by=user)

    def updated_by_current_user(self, *args, **kwargs):
        """
        returns all objects that have been updated by the user (based on the django changeset model)
        """
        user = get_current_user()

        return self.filter(last_modified_by=user)
