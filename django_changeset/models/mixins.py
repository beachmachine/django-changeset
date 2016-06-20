# -*- coding: utf-8 -*-
import logging
from threading import local
from contextlib import contextmanager

from django.db import models
from django.db.models import options
from django.db.models.signals import pre_save, post_save, post_init
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import force_text
from django.contrib.auth.models import User

# import get_model (different versions of django, django.db.models.get_model is deprecated for newer django versions)
try:
    from django.apps import apps
    get_model = apps.get_model
except ImportError:
    # django < 1.7
    from django.db.models import get_model


from django_changeset.models import ChangeSet, ChangeRecord

logger = logging.getLogger(__name__)
_thread_locals = local()

# allow the `track_fields`, `track_by` and `track_related` attributes in the Meta class of
# models. `track_fields` should contain a list of field names for
# which the changes should get tracked. `track_by` the field name by which
# the tracked object should get referenced (defaults to 'id'). `track_related` can be used
# to represent a child - parent relationship of models, where changes on the child should
# be visible in the changes of the parent. `track_related` contains a dict, where the key
# is the name of the foreign key field, and the value the used field-name for the ChangeRecord
# on the parent (usually the `related_name`).
options.DEFAULT_NAMES = options.DEFAULT_NAMES + ('track_fields', 'track_by', 'track_related', 'related_name_user', )



def get_all_objects_created_by_user(user, object_type):
    """
    returns all objects of type "object-type" that have been created by user
    :param user: the user object
    :type: django.contrib.auth.models.User
    :param object_type: the content type object
    :type object_type: django.contrib.contenttypes.models.ContentType
    :return: a list with objects of type `object_type`
    :rtype: list of object_type
    """
    queryset = ChangeSet.objects.filter(user=user, object_type=object_type)

    # first, collect the primary keys (object_uuid) of all change_sets that look like a created object
    pks = []
    for change_set in queryset:
        # get earliest change record
        change_record = change_set.change_records.all().earliest()

        # was this created by the user?
        if change_record.change_set.user == user:
            # must not be related, old value must be none and new value must be not none
            if not change_record.is_related and change_record.old_value is None and change_record.new_value is not None:
                # only add if it has not been added
                if change_set.id not in pks:
                    pks.append(change_set.object_uuid)

    # get the class of this object_type / content_type
    obj_class = get_model(app_label=object_type.app_label, model_name=object_type.model)

    # and return all objects of that class with the given primary keys
    return obj_class.objects.filter(pk__in=pks)


class ChangesetVersionField(models.PositiveIntegerField):
    """
    A positive integer field to track the number of changes on a model (aka the version).
    Every time the model is updated (saved), this number is incremented by one.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', 0)
        super(ChangesetVersionField, self).__init__(*args, **kwargs)


    def formfield(self, **kwargs):
        widget = kwargs.get('widget')
        if widget:
            if issubclass(widget, AdminIntegerFieldWidget):
                widget = ReadonlyInput()
        else:
            widget = forms.HiddenInput
        kwargs['widget'] = widget
        return super(ChangesetVersionField, self).formfield(**kwargs)



class ConcurrentUpdateException(Exception):
    """
    Raised when a model can not be saved due to a concurrent update.
    """
    def __init__(self, orig_data, latest_version_number, *args, **kwargs):
        super(ConcurrentUpdateException, self).__init__(*args, **kwargs)
        self.orig_data = orig_data
        self.latest_version_number = latest_version_number


class RevisionModelMixin(object):
    """ django_changeset uses the RevisionModelMixin as a mixin class, which enables the changeset on a certain
    model """

    # overwrite the constructor so we can patch a foreign key to the user
    def __init__(self, *args, **kwargs):
        super(RevisionModelMixin, self).__init__(*args, **kwargs)
        # register the get method for related_name on the user model
        related_name_user = getattr(self._meta, 'related_name_user', '')

        if related_name_user != '':
            User.add_to_class("get_" + related_name_user,
                              lambda user: # user will be set by the calling object afterwards
                              get_all_objects_created_by_user(user=user,
                                                              object_type=ContentType.objects.get_for_model(self)))

    def get_version_field(self):
        for field in self._meta.fields:
            if isinstance(field, ChangesetVersionField):
                return field
        return None

    """
    Check if version number is the same, and update it
    """
    def update_version_number(self, content_type):
        version_field = self.get_version_field()

        if not version_field:
            # version field not available
            return

        orig_data = content_type.get_object_for_this_type(pk=self.pk)

        old_version = version_field.value_from_object(orig_data)
        new_version = version_field.value_from_object(self)

        if old_version != new_version:
            raise ConcurrentUpdateException(orig_data=orig_data, latest_version_number=old_version)

        setattr(self, version_field.attname, new_version + 1)


    @staticmethod
    def set_enabled(state):
        setattr(_thread_locals, '__django_changeset__is_enabled', state)

    @staticmethod
    def get_enabled():
        return getattr(_thread_locals, '__django_changeset__is_enabled', True)

    @staticmethod
    def set_related_enabled(state):
        setattr(_thread_locals, '__django_changeset__is_related_enabled', state)

    @staticmethod
    def get_related_enabled():
        return getattr(_thread_locals, '__django_changeset__is_related_enabled', True)

    @staticmethod
    @contextmanager
    def enabled(state):
        state_orig = RevisionModelMixin.get_enabled()
        if state == state_orig:
            yield
            return

        RevisionModelMixin.set_enabled(state)
        yield
        RevisionModelMixin.set_enabled(state_orig)

    @staticmethod
    @contextmanager
    def related_enabled(state):
        state_orig = RevisionModelMixin.get_related_enabled()
        if state == state_orig:
            yield
            return

        RevisionModelMixin.set_related_enabled(state)
        yield
        RevisionModelMixin.set_related_enabled(state_orig)

    @property
    def change_sets(self):
        """ Gets all change sets to the current object.

        :returns: a list of changesets
        :rtype: list of django_changeset.models.ChangeSet
        """
        object_uuid_field_name = getattr(self._meta, 'track_by', 'id')
        object_uuid = getattr(self, object_uuid_field_name)
        content_type = ContentType.objects.get_for_model(self)
        return ChangeSet.objects.filter(object_type=content_type, object_uuid=object_uuid)

    @property
    def created_by(self):
        """ Gets the user that created this object

        :returns: the user that created this object
        :rtype: django.contrib.auth.models.User
        """
        earliest_changeset = self._get_earliest_changeset()
        if earliest_changeset:
            try:
                return earliest_changeset.user
            except ObjectDoesNotExist:
                logger.debug(u"No user for the first change set of '%(model)s' with pk '%(pk)s'." % {
                    'model': force_text(earliest_changeset.object_type),
                    'pk': force_text(earliest_changeset.object_uuid),
                })
        return None

    @property
    def created_at(self):
        """ Gets the date when this object was created

        :returns: the date when this object was created
        :rtype: django.db.models.DateTimeField
        """
        earliest_changeset = self._get_earliest_changeset()
        if earliest_changeset:
            return earliest_changeset.date
        return None

    @property
    def last_modified_by(self):
        """
        Gets the user that last modified the object

        :returns: the user that last modified this object
        :rtype: django.contrib.auth.models.User
        """
        latest_changeset = self._get_latest_changeset()
        if latest_changeset:
            try:
                return latest_changeset.user
            except ObjectDoesNotExist:
                logger.debug(u"No user for the latest change set of '%(model)s' with pk '%(pk)s'." % {
                    'model': force_text(latest_changeset.object_type),
                    'pk': force_text(latest_changeset.object_uuid),
                })
        return None

    @property
    def last_modified_at(self):
        """ Gets the date when the object was last modified

        :returns: the date when this object was last modified
        :rtype: django.db.models.DateTimeField
        """
        latest_changeset = self._get_latest_changeset()
        if latest_changeset:
            return latest_changeset.date
        return None

    @property
    def changed_data(self):
        """ Gets a dictionary of changed data

        :returns: a dictionary with the affected field name as key, and the original and new value as content
        :rtype: dict
        """
        changed_fields = {}
        orig_data = getattr(self, '__original_data__', {})

        for field_name in getattr(self._meta, 'track_fields', []):
            orig_value = orig_data.get(field_name)

            try:
                new_value = getattr(self, field_name)
            except ObjectDoesNotExist:
                new_value = None

            if orig_value != new_value:
                changed_fields[field_name] = (orig_value, new_value)

        return changed_fields

    def _persist_related_change(self, related_name, related_uuid):
        """
        Persists a change of an entity referencing this entity. This method
        should be called on the 'parent entity' when saving a 'child entity'
        which should be represented in the 'parent entity' history.

        :param related_name: Name of the related field on the parent entity
        :param object_uuid: UUID of the child entity
        """
        object_uuid_field_name = getattr(self._meta, 'track_by', 'id')
        object_uuid = getattr(self, object_uuid_field_name)
        object_type = ContentType.objects.get_for_model(self)

        change_set = ChangeSet()
        change_set.object_type = object_type
        change_set.object_uuid = object_uuid

        # are there any existing changesets?
        existing_changesets = ChangeSet.objects.filter(object_uuid=object_uuid, object_type=object_type)
        if len(existing_changesets) > 0:
            change_set.changeset_type = change_set.UPDATE_TYPE




        change_set.save()

        change_record = ChangeRecord()
        change_record.change_set = change_set
        change_record.field_name = related_name
        change_record.new_value = related_uuid
        change_record.is_related = True
        change_record.save()

    @staticmethod
    def save_related_revision(sender, **kwargs):
        if not RevisionModelMixin.get_enabled() or not RevisionModelMixin.get_related_enabled():
            return

        new_instance = kwargs['instance']

        object_uuid_field_name = getattr(new_instance._meta, 'track_by', 'id')
        object_related = getattr(new_instance._meta, 'track_related', []) # get meta class attribute 'track_related'

        if isinstance(object_related, dict):
            logger.error('You are using track_related with a dictionary, but this version is expecting a list!')

        object_uuid = getattr(new_instance, object_uuid_field_name)

        # iterate over the list of "track_related" items and get their related object and name
        for fk_field_name in object_related:
            try:
                related_object = getattr(new_instance, fk_field_name)

                if not isinstance(related_object, RevisionModelMixin):
                    raise ObjectDoesNotExist

                # get the related field and the "related_name" (as in: ForeignKey(MyModel, related_name="abcd")
                related_field = new_instance._meta.get_field(fk_field_name)
                related_name = related_field.related_query_name()

                related_object._persist_related_change(related_name, object_uuid)
            except ObjectDoesNotExist:
                pass

    @staticmethod
    def save_initial_model_revision(sender, **kwargs):
        if not RevisionModelMixin.get_enabled():
            return

        new_instance = kwargs['instance']
        raw = kwargs['raw']

        # do not track raw inserts/updates
        if raw or not isinstance(new_instance, RevisionModelMixin):
            return

        object_uuid_field_name = getattr(new_instance._meta, 'track_by', 'id')
        object_uuid = getattr(new_instance, object_uuid_field_name)
        content_type = ContentType.objects.get_for_model(new_instance)

        change_set_count = ChangeSet.objects.filter(object_type=content_type, object_uuid=object_uuid).count()
        if change_set_count > 0:
            return  # if there is already an change-set, we do not need to save a new initial one

        changed_fields = {}
        for field_name in getattr(new_instance._meta, 'track_fields', []):
            try:
                new_value = getattr(new_instance, field_name)
            except ObjectDoesNotExist:
                new_value = None
            changed_fields[field_name] = (None, new_value)

        change_set = ChangeSet()
        change_set.object_type = content_type
        change_set.object_uuid = object_uuid

        # are there any existing changesets?
        existing_changesets = ChangeSet.objects.filter(object_uuid=object_uuid, object_type=content_type)
        if len(existing_changesets) > 0:
            change_set.changeset_type = change_set.UPDATE_TYPE

        change_set.save()

        for changed_field, changed_value in changed_fields.items():
            change_record = ChangeRecord()

            change_record.change_set = change_set
            change_record.field_name = changed_field
            change_record.old_value = changed_value[0]
            change_record.new_value = changed_value[1]
            change_record.save()

        RevisionModelMixin.save_related_revision(sender, **kwargs)

    @staticmethod
    def save_model_revision(sender, **kwargs):
        if not RevisionModelMixin.get_enabled():
            return

        new_instance = kwargs['instance']
        raw = kwargs['raw']

        # do not track raw inserts/updates, as well as regular inserts.
        if raw or not new_instance.pk or not isinstance(new_instance, RevisionModelMixin):
            return

        changed_fields = new_instance.changed_data

        # quit here if there is nothing to track.
        if not changed_fields:
            return

        object_uuid_field_name = getattr(new_instance._meta, 'track_by', 'id')
        content_type = ContentType.objects.get_for_model(new_instance)

        new_instance.update_version_number(content_type)


        change_set = ChangeSet()

        change_set.object_type = content_type
        change_set.object_uuid = getattr(new_instance, object_uuid_field_name)

        # are there any existing changesets?
        existing_changesets = ChangeSet.objects.filter(object_uuid=change_set.object_uuid, object_type=content_type)

        if len(existing_changesets) > 0:
            change_set.changeset_type = change_set.UPDATE_TYPE


        change_set.save()

        for changed_field, changed_value in changed_fields.items():
            change_record = ChangeRecord()

            change_record.change_set = change_set
            change_record.field_name = changed_field
            change_record.old_value = changed_value[0]
            change_record.new_value = changed_value[1]
            change_record.save()

        RevisionModelMixin.save_related_revision(sender, **kwargs)

    @staticmethod
    def save_model_original_data(sender, **kwargs):
        if not RevisionModelMixin.get_enabled():
            return

        instance = kwargs['instance']
        original_data = {}

        # do not save original data if model is not a RevisionModel
        if not isinstance(instance, RevisionModelMixin):
            return

        for field_name in getattr(instance._meta, 'track_fields', []):
            try:
                value = getattr(instance, field_name)
            except (ObjectDoesNotExist, ValueError):
                value = None

            original_data[field_name] = value

        setattr(instance, '__original_data__', original_data)

    def _get_earliest_changeset(self):
        try:
            return self.change_sets.earliest()
        except ChangeSet.DoesNotExist:
            return None

    def _get_latest_changeset(self):
        try:
            return self.change_sets.latest()
        except ChangeSet.DoesNotExist:
            return None


# connect the `pre_save` event to the subscribers for tracking changes. we make use of `dispatch_uid` so the
# event is not connected twice.
post_init.connect(
    RevisionModelMixin.save_model_original_data,
    dispatch_uid="django_changeset.save_model_original_data.subscriber",
)
post_save.connect(
    RevisionModelMixin.save_model_original_data,
    dispatch_uid="django_changeset.save_model_original_data.subscriber",
)
pre_save.connect(
    RevisionModelMixin.save_model_revision,
    dispatch_uid="django_changeset.save_model_revision.subscriber",
)
post_save.connect(
    RevisionModelMixin.save_initial_model_revision,
    dispatch_uid="django_changeset.save_initial_model_revision.subscriber",
)


