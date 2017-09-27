# -*- coding: utf-8 -*-
import logging
from functools import reduce
from threading import local
from contextlib import contextmanager
from django.conf import settings
from django.db import models
from django.db.models import options, ManyToManyRel
from django.db.models.signals import pre_save, post_save, post_init, m2m_changed
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import force_text
from django.contrib.auth.models import User
from django import forms
from django.dispatch import receiver
from django.utils import timezone
from django_userforeignkey.request import get_current_user


# import get_model (different versions of django, django.db.models.get_model is deprecated for newer django versions)
try:
    from django.apps import apps

    get_model = apps.get_model
except ImportError:
    # django < 1.7
    from django.db.models import get_model

from django_changeset.models import ChangeSet, ChangeRecord


def getattr_orm(instance, key):
    """
    Provides a getattr method which does a recursive lookup in the orm, by splitting the key on every occurance of
    __
    :param instance:
    :param key:
    :return:
    """
    return reduce(getattr, [instance] + key.split('__'))


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
options.DEFAULT_NAMES = options.DEFAULT_NAMES + \
                        ('track_fields', 'track_by', 'track_related', 'related_name_user', 'track_through',
                         'track_soft_delete_by',
                         'aggregate_changesets_within_seconds')


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
    # ToDo: This method could use a rewrite
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
    A positive integer field to track the number of changes on a model when RevisionModelMixin is in use.
    In addition to the RevisionModelMixin, you can use the ChangesetVersionField to
    track the number of changes on a model.
    Every time the model is updated (saved), this number is incremented by one.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', 0)
        super(ChangesetVersionField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        kwargs['widget'] = forms.HiddenInput
        # widget = kwargs.get('widget')


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
                              lambda user:  # user will be set by the calling object afterwards
                              get_all_objects_created_by_user(user=user,
                                                              object_type=ContentType.objects.get_for_model(self)))

    def get_version_field(self):
        """ gets the version field by looking in _meta.fields, and checks if it is a ChangesetVersionField """
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

    def check_for_changesets_attribute(self):
        if not hasattr(self, "changesets"):
            raise Exception("""Could not find field "changesets" on the model.
Add the following code to the model that inherits from RevisionModelMixin:

from django.contrib.contenttypes.fields import GenericRelation


class SomeModel(models.Model, RevisionModelMixin):
    # ...            
    changesets = GenericRelation(
        ChangeSet,
        content_type_field='object_type',
        object_id_field='object_uuid'
    )

            """)

    @property
    def created_by(self):
        self.check_for_changesets_attribute()
        return self.changesets.filter(changeset_type='I').first().user

    @property
    def created_at(self):
        self.check_for_changesets_attribute()
        return self.changesets.filter(changeset_type='I').first().date

    @property
    def last_modified_by(self):
        self.check_for_changesets_attribute()
        return self.changesets.last().user

    @property
    def last_modified_at(self):
        self.check_for_changesets_attribute()
        return self.changesets.last().date

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
                # check if is foreign key --> if yes, only get the id (--> not a db lookup)
                field = self._meta.get_field(field_name)

                if field.rel:
                    # related field, get the id
                    if isinstance(field.rel, ManyToManyRel):
                        # many to many related fields are special, we need to fetch the IDs using the manager
                        new_value = ",".join([str(item) for item in getattr(self, field_name).all().values_list('id', flat=True)])
                    else:
                        new_value = getattr(self, field_name + "_id")
                else:
                    new_value = getattr(self, field_name)
            except ObjectDoesNotExist:
                new_value = None

            # check if value has changed, and store it in changed_fields
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
        if existing_changesets.exists():
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
        object_related = getattr(new_instance._meta, 'track_related', [])  # get meta class attribute 'track_related'

        if isinstance(object_related, dict):
            logger.error('You are using track_related with a dictionary, but this version is expecting a list!')

        object_uuid = getattr_orm(new_instance, object_uuid_field_name)

        # iterate over the list of "track_related" items and get their related object and name
        for fk_field_name in object_related:
            try:
                related_object = getattr_orm(new_instance, fk_field_name)

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

        # do not track raw inserts/updates (e.g. fixtures)
        if kwargs.get('raw'):
            return

        new_instance = kwargs['instance']

        # check if this is a revision model
        if not isinstance(new_instance, RevisionModelMixin):
            return

        object_uuid_field_name = getattr(new_instance._meta, 'track_by', 'id')
        object_uuid = getattr_orm(new_instance, object_uuid_field_name)
        content_type = ContentType.objects.get_for_model(new_instance)

        change_set_count = ChangeSet.objects.filter(object_type=content_type, object_uuid=object_uuid).count()
        if change_set_count > 0:
            return  # if there is already an change-set, we do not need to save a new initial one

        changed_fields = {}
        for field_name in getattr(new_instance._meta, 'track_fields', []):
            try:
                # check if is foreign key --> if yes, only get the id (--> not a db lookup)
                field = new_instance._meta.get_field(field_name)

                if field.rel:
                    # related field, get the id
                    if isinstance(field.rel, ManyToManyRel):
                        # many to many related fields are special, we need to fetch the IDs using the manager
                        new_value = ",".join([str(item) for item in getattr(new_instance, field_name).all().values_list('id', flat=True)])
                    else:
                        new_value = getattr_orm(new_instance, field_name + "_id")
                else:
                    new_value = getattr(new_instance, field_name)
            except ObjectDoesNotExist:
                new_value = None
            changed_fields[field_name] = (None, new_value)

        change_set = ChangeSet()
        change_set.object_type = content_type
        change_set.object_uuid = object_uuid

        # are there any existing changesets?
        existing_changesets = ChangeSet.objects.filter(object_uuid=object_uuid, object_type=content_type)
        if existing_changesets.exists():
            change_set.changeset_type = change_set.UPDATE_TYPE

        change_set.save()

        change_records = []

        # collect change records
        for changed_field, changed_value in changed_fields.items():
            change_record = ChangeRecord(
                change_set=change_set, field_name=changed_field,
                old_value=changed_value[0], new_value=changed_value[1]
            )

            change_records.append(change_record)

        # bulk create change records
        ChangeRecord.objects.bulk_create(change_records)

        RevisionModelMixin.save_related_revision(sender, **kwargs)

    @staticmethod
    def m2m_changed(sender, **kwargs):
        if not RevisionModelMixin.get_enabled():
            return

        action = kwargs['action']

        # only react on post_add and post_remove (this is also checked 30 lines below)
        if action not in ['post_add', 'post_remove']:
            return

        # get instance, primary key set and the action
        instance = kwargs['instance']
        pk_set = kwargs['pk_set']

        track_through_fields = getattr(instance._meta, 'track_through', [])

        for field_name in track_through_fields:
            field = getattr(instance, field_name)
            if field.through == sender:
                # track change on field_name
                print('Action ', action, ' on field ', field_name, ': ', pk_set)

                # check if changeset exists
                if hasattr(instance, '__m2m_change_set__'):
                    # use existing change set
                    change_set = getattr(instance, '__m2m_change_set__')
                else:
                    # create a new change set
                    content_type = ContentType.objects.get_for_model(instance)
                    object_uuid_field_name = getattr(instance._meta, 'track_by', 'id')

                    change_set = ChangeSet()

                    change_set.object_type = content_type
                    change_set.object_uuid = getattr_orm(instance, object_uuid_field_name)

                    change_set.changeset_type = change_set.UPDATE_TYPE

                    change_set.save()
                    # store this changeset in instance, in case we get another update soon
                    setattr(instance, '__m2m_change_set__', change_set)

                # iterate over the list of primary keys
                for pk in pk_set:
                    # create a new change record for each PK
                    change_record = ChangeRecord()

                    change_record.change_set = change_set
                    change_record.field_name = field_name

                    if action == 'post_add':
                        # in case of an add, we store the new value (old value is None by default)
                        change_record.new_value = pk
                    elif action == 'post_remove':
                        # in case of a delete, we store the old value (new value is None by default)
                        change_record.old_value = pk

                    # save the change record
                    change_record.save()
                    # end for
                    # end if
                    # end for field_name in track_through_fields

    @staticmethod
    def update_model_version_number(sender, **kwargs):
        if not RevisionModelMixin.get_enabled():
            return

        # do not track raw inserts/updates (e.g. fixtures)
        if kwargs.get('raw'):
            return

        new_instance = kwargs['instance']

        # check if this is a revision model
        if not new_instance.pk or not isinstance(new_instance, RevisionModelMixin):
            return

        changed_fields = new_instance.changed_data

        # quit here if there is nothing to track.
        if not changed_fields:
            return

        object_uuid_field_name = getattr(new_instance._meta, 'track_by', 'id')
        content_type = ContentType.objects.get_for_model(new_instance)
        object_uuid = getattr_orm(new_instance, object_uuid_field_name)

        # are there any existing changesets?
        existing_changesets = ChangeSet.objects.filter(object_uuid=object_uuid, object_type=content_type)

        if existing_changesets.exists():
            new_instance.update_version_number(content_type)

    @staticmethod
    def save_model_revision(sender, **kwargs):
        if not RevisionModelMixin.get_enabled():
            return

        # do not track raw inserts/updates (e.g. fixtures)
        if kwargs.get('raw'):
            return

        new_instance = kwargs['instance']

        # check if this is a revision model
        if not new_instance.pk or not isinstance(new_instance, RevisionModelMixin):
            return

        changed_fields = new_instance.changed_data

        # quit here if there is nothing to track.
        if not changed_fields:
            return

        # determine whether this is a soft delete or a restore operation
        is_soft_delete = False
        is_restore = False

        # get track_soft_deleted_by from the current model
        track_soft_delete_by = getattr(new_instance._meta, 'track_soft_delete_by', None)
        if track_soft_delete_by and track_soft_delete_by in changed_fields:
            if len(changed_fields) > 1:
                raise Exception("""Can not modify more than one field if track_soft_delete_by is changed""")

            # determine whether this is a soft delete or a trash
            change_record = changed_fields[track_soft_delete_by]

            if change_record[1] is True:
                is_soft_delete = True
            else:
                is_restore = True

        object_uuid_field_name = getattr(new_instance._meta, 'track_by', 'id')
        content_type = ContentType.objects.get_for_model(new_instance)

        change_set = ChangeSet()

        change_set.object_type = content_type
        change_set.object_uuid = getattr_orm(new_instance, object_uuid_field_name)

        # are there any existing changesets (without restore/soft_delete)?
        existing_changesets = ChangeSet.objects.filter(
            object_uuid=change_set.object_uuid,
            object_type=content_type
        ).exclude(
            changeset_type__in=[ChangeSet.RESTORE_TYPE, ChangeSet.SOFT_DELETE_TYPE]
        )

        last_changeset = None

        update_existing_changeset = False

        if existing_changesets.exists():
            # an existing changeset already exists
            # the operation performed can be either soft delete, restore or update
            if is_soft_delete:
                change_set.changeset_type = change_set.SOFT_DELETE_TYPE
            elif is_restore:
                change_set.changeset_type = change_set.RESTORE_TYPE
            else:
                change_set.changeset_type = change_set.UPDATE_TYPE
                # get the latest changeset, so we can check if the latest of existing_changeset was created by the
                # current user within the last couple of seconds
                last_changeset = existing_changesets.latest()

        # check if last changeset was created by the current user within the last couple of seconds
        if last_changeset \
                and last_changeset.user == get_current_user() \
                and last_changeset.date > timezone.now()-timezone.timedelta(
                    seconds=getattr(new_instance._meta, 'aggregate_changesets_within_seconds', 0)
                ):
            # overwrite the new_changeset
            logger.debug("Re-using last changeset")
            change_set = last_changeset
            change_set.date = timezone.now()
            update_existing_changeset = True

        change_set.save()

        if update_existing_changeset:
            # updateing an existing changeset: need to check all change records for their existance
            check_number_of_change_records = False

            for changed_field, changed_value in changed_fields.items():
                # if the changerecord for a change_set and a field already exists, it needs to be updated
                change_record, created = ChangeRecord.objects.get_or_create(
                    change_set=change_set, field_name=changed_field,
                    defaults={'old_value': changed_value[0], 'new_value': changed_value[1]},
                )

                if not created:
                    # it already exists, therefore we need to update new value
                    change_record.new_value = changed_value[1]

                    # check if old value and new value are the same
                    if change_record.new_value == change_record.old_value:
                        # delete this change record
                        change_record.delete()
                        check_number_of_change_records = True
                    else:
                        # save this change record
                        change_record.save()

            # we deleted a change record, lets make sure a change record still exists
            if check_number_of_change_records:
                if not change_set.change_records.all().exists():
                    # no change record exists for this changeset --> delete the change set
                    change_set.delete()

        else:
            # collect change records
            change_records = []

            # iterate over all changed fields and create a change record for them
            for changed_field, changed_value in changed_fields.items():
                change_record = ChangeRecord(
                    change_set=change_set, field_name=changed_field,
                    old_value=changed_value[0], new_value=changed_value[1]
                )
                change_records.append(change_record)

            # do a bulk create to increase database performance
            ChangeRecord.objects.bulk_create(change_records)

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
                # check if is foreign key --> if yes, get id
                field = instance._meta.get_field(field_name)

                if field.rel:
                    # related field, get the id
                    if isinstance(field.rel, ManyToManyRel):
                        # many to many related fields are special, we need to fetch the IDs using the manager
                        value = ",".join([str(item) for item in getattr(instance, field_name).all().values_list('id', flat=True)])
                    else:
                        value = getattr_orm(instance, field_name + "_id")
                else:
                    value = getattr_orm(instance, field_name)
            except (ObjectDoesNotExist, ValueError):
                value = None

            original_data[field_name] = value

        setattr(instance, '__original_data__', original_data)


# on post init: store the original data (e.g., when the model is loaded from the database the first time)
post_init.connect(
    RevisionModelMixin.save_model_original_data,
    dispatch_uid="django_changeset.save_model_original_data.subscriber",
)
# on pre save: update version number
pre_save.connect(
    RevisionModelMixin.update_model_version_number,
    dispatch_uid="django_changeset.update_model_version_number.subscriber"
)
# on post save: save model changes (changes are determined based on original model data)
post_save.connect(
    RevisionModelMixin.save_model_revision,
    dispatch_uid="django_changeset.save_model_revision.subscriber",
)
# after that: store the changed data as the "new" original data again
post_save.connect(
    RevisionModelMixin.save_model_original_data,
    dispatch_uid="django_changeset.save_model_original_data.subscriber",
)
post_save.connect(
    RevisionModelMixin.save_initial_model_revision,
    dispatch_uid="django_changeset.save_initial_model_revision.subscriber",
)
# many to many (m2m) hook
m2m_changed.connect(
    RevisionModelMixin.m2m_changed,
    dispatch_uid="django_changeset.m2m_changed.subscriber",
)

