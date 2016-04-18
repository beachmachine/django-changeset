# -*- coding: utf-8 -*-
import logging

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text

from django_userforeignkey.models.fields import UserForeignKey

logger = logging.getLogger(__name__)


class ChangeSet(models.Model):
    date = models.DateTimeField(
        verbose_name=_(u"Date"),
        auto_now_add=True,
        editable=False,
        null=False,
    )

    user = UserForeignKey(
        verbose_name=_(u"User"),
        auto_user_add=True,
    )

    object_type = models.ForeignKey(
        ContentType,
        verbose_name=_(u"Object type"),
        editable=False,
        null=False,
    )

    object_uuid = models.CharField(
        verbose_name=_(u"Object UUID"),
        max_length=255,
        editable=False,
    )

    class Meta:
        app_label = 'django_changeset'
        get_latest_by = 'date'
        ordering = ['-date', ]

    def __unicode__(self):
        return _(u"Change on %(app_label)s.%(model)s %(uuid)s at date %(date)s by %(user)s") % {
            'app_label': self.object_type.app_label,
            'model': self.object_type.model,
            'uuid': self.object_uuid,
            'date': self.date,
            'user': self.user,
        }

    def __str__(self):
        return self.__unicode__()

class ChangeRecord(models.Model):
    change_set = models.ForeignKey(
        ChangeSet,
        related_name="change_records",
        null=False,
        editable=False,
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
    def field_verbose_name(self):
        field = self._get_field()

        if field:
            return field.verbose_name
        return self.field_name.capitalize().replace('_', ' ')

    @property
    def old_value_display(self):
        field = self._get_field()

        if field and isinstance(field, models.ForeignKey):
            return self._get_object_or_none(field.rel.to, pk=self.old_value)
        elif field and hasattr(field, 'flatchoices'):
            return force_text(dict(field.flatchoices).get(self.old_value, self.old_value), strings_only=True)

        return self.old_value

    @property
    def new_value_display(self):
        field = self._get_field()

        if field and isinstance(field, models.ForeignKey):
            return self._get_object_or_none(field.rel.to, pk=self.new_value)
        elif field and hasattr(field, 'flatchoices'):
            return force_text(dict(field.flatchoices).get(self.new_value, self.new_value), strings_only=True)

        return self.new_value
