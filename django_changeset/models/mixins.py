# -*- coding: utf-8 -*-
import logging

from threading import local

from contextlib import contextmanager

from django.db.models import options
from django.db.models.signals import pre_save, post_save, post_init
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import force_text

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
options.DEFAULT_NAMES = options.DEFAULT_NAMES + ('track_fields', 'track_by', 'track_related', )


class RevisionModelMixin(object):

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
        """
        Gets all change sets to the current object.
        """
        object_uuid_field_name = getattr(self._meta, 'track_by', 'id')
        object_uuid = getattr(self, object_uuid_field_name)
        content_type = ContentType.objects.get_for_model(self)
        return ChangeSet.objects.filter(object_type=content_type, object_uuid=object_uuid)

    @property
    def created_by(self):
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
        earliest_changeset = self._get_earliest_changeset()
        if earliest_changeset:
            return earliest_changeset.date
        return None

    @property
    def last_modified_by(self):
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
        latest_changeset = self._get_latest_changeset()
        if latest_changeset:
            return latest_changeset.date
        return None

    @property
    def changed_data(self):
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
        object_related = getattr(new_instance._meta, 'track_related', {})
        object_uuid = getattr(new_instance, object_uuid_field_name)

        for fk_field_name, related_name in object_related.items():
            try:
                related_object = getattr(new_instance, fk_field_name)

                if not isinstance(related_object, RevisionModelMixin):
                    raise ObjectDoesNotExist

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
        change_set = ChangeSet()

        change_set.object_type = content_type
        change_set.object_uuid = getattr(new_instance, object_uuid_field_name)
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
