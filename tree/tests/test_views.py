from django.test import TestCase, Client

from tree.models import Person, EditLog


class TreeTestCase(TestCase):
    def setUp(self):
        self.root = Person.objects.create(first_name='الجد', gender='M')
        self.son1 = Person.objects.create(first_name='محمد', gender='M', father=self.root)
        self.son2 = Person.objects.create(first_name='أحمد', gender='M', father=self.root)
        self.grandson1 = Person.objects.create(first_name='خالد', gender='M', father=self.son1)
        self.grandson2 = Person.objects.create(first_name='عمر', gender='M', father=self.son1)
        self.daughter = Person.objects.create(first_name='فاطمة', gender='F', father=self.son1)

    def _clear_tree(self):
        Person.objects.update(father=None, mother=None)
        Person.objects.all().delete()


class PublicAccessTests(TreeTestCase):
    """The app is open — no login required for any page or endpoint."""

    def test_tree_view_anonymous(self):
        self.assertEqual(Client().get('/').status_code, 200)

    def test_healthz(self):
        self.assertEqual(Client().get('/healthz/').status_code, 200)

    def test_tree_data_anonymous(self):
        resp = Client().get('/api/tree/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['tree']['name'], 'الجد')

    def test_person_detail_anonymous(self):
        self.assertEqual(Client().get(f'/api/person/{self.son1.id}/').status_code, 200)

    def test_edit_form_and_log_render(self):
        c = Client()
        self.assertEqual(c.get(f'/api/person/{self.son1.id}/edit-form/').status_code, 200)
        self.assertEqual(c.get(f'/api/person/{self.son1.id}/edit-log/').status_code, 200)

    def test_single_header(self):
        html = Client().get('/').content.decode()
        self.assertEqual(html.count('class="tree-topbar'), 1)
        self.assertNotIn('id="site-header"', html)
        self.assertIn('tree-heading-title', html)
        self.assertIn('class="tree-toolbar', html)


class TreeViewTests(TreeTestCase):
    def test_tree_data_returns_nested_tree(self):
        data = Client().get('/api/tree/').json()
        root = data['tree']
        self.assertEqual(root['name'], 'الجد')
        self.assertEqual(len(root['children']), 2)

    def test_tree_data_404_without_root(self):
        self._clear_tree()
        resp = Client().get('/api/tree/')
        self.assertEqual(resp.status_code, 404)

    def test_tree_view_shows_add_root_when_empty(self):
        self._clear_tree()
        resp = Client().get('/')
        self.assertContains(resp, 'add-root-panel')

    def test_edit_button_visible_publicly(self):
        resp = Client().get(f'/api/person/{self.son1.id}/')
        self.assertContains(resp, 'تعديل')


class AddRootTests(TreeTestCase):
    def test_add_root_rejected_when_one_exists(self):
        resp = Client().post('/api/root/add/', {'first_name': 'آخر'})
        self.assertEqual(resp.status_code, 400)

    def test_add_root_success(self):
        self._clear_tree()
        resp = Client().post('/api/root/add/', {'first_name': 'الجد'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(Person.objects.filter(father__isnull=True).count(), 1)

    def test_add_root_requires_name(self):
        self._clear_tree()
        resp = Client().post('/api/root/add/', {'first_name': '  '})
        self.assertEqual(resp.status_code, 400)


class AddChildTests(TreeTestCase):
    def test_add_child_success(self):
        resp = Client().post(f'/api/person/{self.son1.id}/add-child/',
                             {'first_name': 'يوسف', 'gender': 'M'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertTrue(Person.objects.filter(first_name='يوسف', father=self.son1).exists())

    def test_add_child_to_female_forbidden(self):
        resp = Client().post(f'/api/person/{self.daughter.id}/add-child/',
                             {'first_name': 'سالم', 'gender': 'M'})
        self.assertEqual(resp.status_code, 403)

    def test_add_child_requires_name(self):
        resp = Client().post(f'/api/person/{self.son1.id}/add-child/',
                             {'first_name': '', 'gender': 'M'})
        self.assertEqual(resp.status_code, 400)


class UpdatePersonTests(TreeTestCase):
    def test_update_person_fields(self):
        resp = Client().post(f'/api/person/{self.son1.id}/update/', {
            'first_name': 'محمد', 'birth_year': '1990', 'phone': '+96899999999',
            'house_location': '', 'education': 'جامعي', 'occupation': 'مهندس',
            'is_deceased': 'on', 'death_year': '2020',
        })
        self.assertEqual(resp.status_code, 200)
        self.son1.refresh_from_db()
        self.assertEqual(self.son1.birth_year, 1990)
        self.assertEqual(self.son1.education, 'جامعي')
        self.assertTrue(self.son1.is_deceased)
        self.assertEqual(self.son1.death_year, 2020)
        self.assertTrue(EditLog.objects.filter(person=self.son1, field_name='education').exists())

    def test_unchecking_deceased_clears_death_year(self):
        self.son1.is_deceased = True
        self.son1.death_year = 2000
        self.son1.save()
        Client().post(f'/api/person/{self.son1.id}/update/', {
            'first_name': 'محمد', 'birth_year': '', 'phone': '',
            'house_location': '', 'education': '', 'occupation': '',
        })
        self.son1.refresh_from_db()
        self.assertFalse(self.son1.is_deceased)
        self.assertIsNone(self.son1.death_year)


class DeletePersonTests(TreeTestCase):
    def test_delete_leaf(self):
        resp = Client().post(f'/api/person/{self.daughter.id}/delete/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Person.objects.filter(id=self.daughter.id).exists())

    def test_delete_person_with_children_rejected(self):
        resp = Client().post(f'/api/person/{self.son1.id}/delete/')
        self.assertEqual(resp.status_code, 400)

    def test_delete_root_rejected(self):
        resp = Client().post(f'/api/person/{self.root.id}/delete/')
        self.assertEqual(resp.status_code, 400)


class MovePersonTests(TreeTestCase):
    def test_move_person(self):
        resp = Client().post(f'/api/person/{self.grandson1.id}/move/',
                             {'new_father_id': self.son2.id})
        self.assertEqual(resp.status_code, 200)
        self.grandson1.refresh_from_db()
        self.assertEqual(self.grandson1.father_id, self.son2.id)

    def test_move_into_descendant_rejected(self):
        resp = Client().post(f'/api/person/{self.son1.id}/move/',
                             {'new_father_id': self.grandson1.id})
        self.assertEqual(resp.status_code, 400)

    def test_move_root_rejected(self):
        resp = Client().post(f'/api/person/{self.root.id}/move/',
                             {'new_father_id': self.son1.id})
        self.assertEqual(resp.status_code, 400)


class SetMotherTests(TreeTestCase):
    def test_set_and_clear_mother(self):
        mom = Person.objects.create(first_name='أمينة', gender='F')
        resp = Client().post(f'/api/person/{self.son1.id}/set-mother/', {'mother_id': mom.id})
        self.assertEqual(resp.status_code, 200)
        self.son1.refresh_from_db()
        self.assertEqual(self.son1.mother_id, mom.id)

        Client().post(f'/api/person/{self.son1.id}/set-mother/', {'mother_id': ''})
        self.son1.refresh_from_db()
        self.assertIsNone(self.son1.mother_id)

    def test_male_mother_rejected(self):
        resp = Client().post(f'/api/person/{self.son1.id}/set-mother/',
                             {'mother_id': self.son2.id})
        self.assertEqual(resp.status_code, 400)

    def test_apply_mother_to_siblings(self):
        mom = Person.objects.create(first_name='أمينة', gender='F')
        resp = Client().post(f'/api/person/{self.son1.id}/set-mother/',
                             {'mother_id': mom.id, 'apply_siblings': '1'})
        self.assertEqual(resp.status_code, 200)
        self.son2.refresh_from_db()
        self.assertEqual(self.son2.mother_id, mom.id)


class SearchTests(TreeTestCase):
    def test_search_by_first_name(self):
        resp = Client().get('/api/search/?q=خالد')
        self.assertContains(resp, 'خالد')

    def test_search_requires_two_chars(self):
        resp = Client().get('/api/search/?q=خ')
        self.assertEqual(len(resp.context['results']), 0)


class RelationshipTests(TreeTestCase):
    def test_find_relationship(self):
        resp = Client().get(f'/api/relationship/?a={self.root.id}&b={self.grandson1.id}')
        self.assertEqual(resp.status_code, 200)

    def test_relationship_requires_two_people(self):
        resp = Client().get('/api/relationship/?a=0&b=0')
        self.assertEqual(resp.status_code, 400)


class StatsAndExportTests(TreeTestCase):
    def test_tree_stats(self):
        resp = Client().get('/api/stats/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_persons'], 6)

    def test_branch_stats(self):
        resp = Client().get(f'/api/branch-stats/{self.root.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total'], 6)

    def test_export_csv(self):
        resp = Client().get('/api/export/csv/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('الجد', resp.content.decode('utf-8'))
