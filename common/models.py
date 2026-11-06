from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def positive(field):
    return models.CheckConstraint(
        condition=Q(**{f"{field}__gt": 0}),
        name=f"%(app_label)s_%(class)s_{field}_positive",
    )


def nonnegative(field):
    return models.CheckConstraint(
        condition=Q(**{f"{field}__gte": 0}),
        name=f"%(app_label)s_%(class)s_{field}_nonnegative",
    )


def band_constraint(field):
    return models.CheckConstraint(
        condition=Q(**{f"{field}__isnull": True})
        | Q(**{f"{field}__in": [Decimal(i) / 2 for i in range(19)]}),
        name=f"%(app_label)s_%(class)s_{field}_valid",
    )


def validate_band(value):
    if value is not None and (value < 0 or value > 9 or value * 2 % 1):
        raise ValidationError("Band must be 0–9 in steps of 0.5.")
