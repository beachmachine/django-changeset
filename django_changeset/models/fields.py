# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation


class ChangeSetRelation(GenericRelation):

    def __init__(self, object_id_field='object_id', **kwargs):
        from django_changeset.models import ChangeSet

        # ToDo: Add Automatic support for object_id when the related field is an int, and object_uuid when the related
        # field is a UUIDField
        assert(object_id_field in ['object_id', 'object_uuid'])

        kwargs['content_type_field'] = 'object_type'

        super(ChangeSetRelation, self).__init__(
            ChangeSet,
            object_id_field=object_id_field,
            **kwargs
        )
