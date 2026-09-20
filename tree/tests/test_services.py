from django.test import TestCase

from tree.models import Person
from tree import person_service


class PersonServiceTests(TestCase):
    def setUp(self):
        self.root = Person.objects.create(first_name='الجد', gender='M')
        self.child = Person.objects.create(first_name='ابن', gender='M', father=self.root)

    def test_update_creates_logs_only_for_changes(self):
        logs = person_service.update_person(self.child, {'first_name': 'ابن', 'phone': '123'})
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].field_name, 'phone')

    def test_delete_leaf(self):
        person_service.delete_person(self.child)
        self.assertFalse(Person.objects.filter(id=self.child.id).exists())

    def test_delete_root_raises(self):
        with self.assertRaises(ValueError):
            person_service.delete_person(self.root)

    def test_add_child_requires_name(self):
        with self.assertRaises(ValueError):
            person_service.add_child(self.root, {'first_name': '', 'gender': 'M'})

    def test_add_child_to_female_raises(self):
        mom = Person.objects.create(first_name='أم', gender='F')
        with self.assertRaises(ValueError):
            person_service.add_child(mom, {'first_name': 'س', 'gender': 'M'})

    def test_set_mother_cycle_rejected(self):
        mom = Person.objects.create(first_name='أم', gender='F')
        person_service.set_mother(self.child, mom)
        with self.assertRaises(ValueError):
            person_service.set_mother(mom, self.child)
