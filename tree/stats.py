from django.db.models import Q, Count
from .models import Person


def get_aggregate_stats():
    total = Person.objects.count()
    counts = Person.objects.aggregate(
        total_male=Count('id', filter=Q(gender='M')),
        total_female=Count('id', filter=Q(gender='F')),
        total_alive=Count('id', filter=Q(is_deceased=False)),
        total_deceased=Count('id', filter=Q(is_deceased=True)),
    )
    return {
        'total_persons': total,
        **counts,
    }
