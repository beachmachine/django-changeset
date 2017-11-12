# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import logging
import uuid

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text

from django_userforeignkey.models.fields import UserForeignKey

logger = logging.getLogger(__name__)

changeset_related_object = getattr(settings, "DJANGO_CHANGESET_SELECT_RELATED", ["user"])


class ChangeSetManager(models.Manager):
    """
    ChangeSet Manager that forces all ChangeSet queries to contain at least the "user" foreign relation
    """
    def get_queryset(self):
        return super(ChangeSetManager, self).get_queryset().select_related(
            *changeset_related_object
        )


class AbstractChangeSet(models.Model):
    """ Basic changeset/revision model which contains the ``user`` that modified the object ``object_type`` """
    objects = ChangeSetManager()

    # choices for changeset type (insert, update, delete)
    INSERT_TYPE = 'I'
    UPDATE_TYPE = 'U'
    DELETE_TYPE = 'D'
    SOFT_DELETE_TYPE = 'S'
    RESTORE_TYPE = 'R'

    CHANGESET_TYPE_CHOICES = (
        (INSERT_TYPE, 'Insert'),
        (UPDATE_TYPE, 'Update'),
        (DELETE_TYPE, 'Delete'),
        (SOFT_DELETE_TYPE, 'Soft Delete'),
        (RESTORE_TYPE, 'Restore')
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_(u"Primary Key as Python UUID4 Field")
    )

    changeset_type = models.CharField(
        max_length=1,
        verbose_name=_(u"Changeset Type"),
        choices=CHANGESET_TYPE_CHOICES,
        default=INSERT_TYPE,
        editable=False,
        null=False,
        db_index=True
    )

    date = models.DateTimeField(
        verbose_name=_(u"Date"),
        auto_now_add=True,
        editable=False,
        null=False,
        db_index=True
    )

    # track the user that triggered this change
    user = UserForeignKey(
        verbose_name=_(u"User"),
        auto_user_add=True,
        related_name="all_changes", # allows to access userobj.all_changes
    )

    object_type = models.ForeignKey(
        ContentType,
        verbose_name=_(u"Object type"),
        editable=False,
        null=False,
        on_delete=models.CASCADE
    )

    class Meta:
        app_label = 'django_changeset'
        get_latest_by = 'date'
        ordering = ['-date', ]
        abstract = True

    def __unicode__(self):
        return _(u"%(changeset_type)s on %(app_label)s.%(model)s %(uuid)s at date %(date)s by %(user)s") % {
            'changeset_type': self.get_changeset_type_display(),
            'app_label': self.object_type.app_label,
            'model': self.object_type.model,
            'uuid': self.object_uuid,
            'date': self.date,
            'user': self.user,
        }

    def __str__(self):
        return self.__unicode__()


class ChangeSet(AbstractChangeSet):
    object_id = models.BigIntegerField(
        verbose_name=_(u"Object ID"),
        editable=False,
        null=True,
        db_index=True,
    )

    object_uuid = models.UUIDField(
        verbose_name=_(u"Object UUID"),
        editable=False,
        null=True,
        db_index=True,
    )


class ChangeRecord(models.Model):
    """ A change_record represents detailed change information, like which field was changed and what the old aswell as
    the new value of the field look like. It is related to a ``change_set``.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_(u"Primary Key as Python UUID4 Field")
    )

    change_set = models.ForeignKey(
        ChangeSet,
        related_name="change_records",
        null=False,
        editable=False,
        on_delete=models.CASCADE
    )

    field_name = models.CharField(
        verbose_name=_(u"Field name"),
        max_length=255,
        editable=False,
        null=False,
    )

    old_value = models.TextField(
        verbose_name=_(u"Old value"),
        editable=False,
        null=True,
        blank=True,
    )

    new_value = models.TextField(
        verbose_name=_(u"New value"),
        editable=False,
        null=True,
        blank=True,
    )

    is_related = models.BooleanField(
        verbose_name=_(u"Is change on related entity"),
        editable=False,
        null=False,
        default=False,
    )

    class Meta:
        app_label = 'django_changeset'
        get_latest_by = 'change_set__date'
        ordering = ['-change_set__date', 'field_name', ]

    def __unicode__(self):
        return _(u"%(label)s: '%(from)s' to '%(to)s'") % {
            'label': force_text(self.field_verbose_name),
            'from': force_text(self.old_value_display),
            'to': force_text(self.new_value_display),
        }

    def __str__(self):
        return self.__unicode__()

    def _get_related_object(self):
        if not self.is_related:
            return

        related_class = self._get_related_class()

        if not related_class:
            return

        try:
            return related_class.objects.get(pk=self.new_value)
        except related_class.DoesNotExist:
            logger.warning(u"Related object of model '%(model)s' with pk '%(pk)s' does not exist." % {
                'model': force_text(related_class),
                'pk': force_text(self.new_value),
            })

            return None

    def _get_field(self, supress_warning=False):
        model_class = self.change_set.object_type.model_class()

        # try to find the field for the records field_name
        for field in model_class._meta.fields:
            if field.attname == self.field_name:
                return field

        # no field for the field_name found
        if not supress_warning:
            logger.warning(u"Field for this change record does not exist on model '%s'." % force_text(model_class))

        return None

    def _get_relation(self):
        model_class = self.change_set.object_type.model_class()

        # try to find the relation for the records field_name
        for rel in model_class._meta.related_objects:
            if rel.related_name == self.field_name:
                return rel

        # no relation for the field_name found
        logger.warning(u"Relation for this change record does not exist on model '%s'." % force_text(model_class))

        return None

    def _get_related_class(self):
        field = self._get_field(supress_warning=True) # get the field, but dont log a warning
        if field:
            return field.rel.to

        relation = self._get_relation()
        if relation:
            return relation.related_model

        return None

    def _get_object_or_none(self, model_class, **kwargs):
        try:
            return model_class.objects.get(**kwargs)
        except model_class.DoesNotExist:
            return None

    @property
    def related_object(self):
        """ returns the related object (only if the change was on a related entity; check obj.is_related) """
        return self._get_related_object()

    @property
    def field_verbose_name(self):
        """ returns the verbose name of the affected field """
        field = self._get_field(supress_warning=True)

        if field:
            return field.verbose_name
        return self.field_name.capitalize().replace('_', ' ')

    @property
    def old_value_display(self):
        """ returns the old/original value (display) """
        field = self._get_field(supress_warning=True)

        if field and isinstance(field, models.ForeignKey):
            return self._get_object_or_none(field.rel.to, pk=self.old_value)
        elif field and hasattr(field, 'flatchoices'):
            return force_text(dict(field.flatchoices).get(self.old_value, self.old_value), strings_only=True)

        return self.old_value

    @property
    def new_value_display(self):
        """ returns the new value (display) """
        field = self._get_field(supress_warning=True)

        if field and isinstance(field, models.ForeignKey):
            return self._get_object_or_none(field.rel.to, pk=self.new_value)
        elif field and hasattr(field, 'flatchoices'):
            return force_text(dict(field.flatchoices).get(self.new_value, self.new_value), strings_only=True)

        return self.new_value
