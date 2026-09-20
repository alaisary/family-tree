from django.test import TestCase
from tree.models import Person
from tree.stats import get_aggregate_stats


class AggregateStatsTests(TestCase):
    def test_returns_correct_counts(self):
        root = Person.objects.create(first_name='جد', gender='M')
        Person.objects.create(first_name='ابن', gender='M', father=root)
        Person.objects.create(first_name='بنت', gender='F', father=root, is_deceased=True, death_year=2020)

        result = get_aggregate_stats()

        self.assertEqual(result['total_persons'], 3)
        self.assertEqual(result['total_male'], 2)
        self.assertEqual(result['total_female'], 1)
        self.assertEqual(result['total_alive'], 2)
        self.assertEqual(result['total_deceased'], 1)
