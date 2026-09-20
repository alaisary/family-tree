from django.test import TestCase
from tree.models import Person
from tree.tree_utils import (
    build_children_map, get_subtree_ids, get_generation_map, find_relationship,
)


class BuildChildrenMapTests(TestCase):
    def test_empty_tree_returns_empty_dict(self):
        result = build_children_map()
        self.assertEqual(result, {})

    def test_maps_father_to_children(self):
        root = Person.objects.create(first_name='جد', gender='M')
        son1 = Person.objects.create(first_name='أب١', gender='M', father=root)
        son2 = Person.objects.create(first_name='أب٢', gender='M', father=root)
        grandson = Person.objects.create(first_name='حفيد', gender='M', father=son1)

        result = build_children_map()

        self.assertCountEqual(result[root.id], [son1.id, son2.id])
        self.assertEqual(result[son1.id], [grandson.id])
        self.assertNotIn(son2.id, result)
        self.assertNotIn(grandson.id, result)


class GetSubtreeIdsTests(TestCase):
    def test_leaf_node_returns_self(self):
        root = Person.objects.create(first_name='جد', gender='M')
        son = Person.objects.create(first_name='ابن', gender='M', father=root)

        result = get_subtree_ids(son.id)

        self.assertEqual(result, {son.id})

    def test_returns_all_descendants(self):
        root = Person.objects.create(first_name='جد', gender='M')
        son = Person.objects.create(first_name='ابن', gender='M', father=root)
        grandson = Person.objects.create(first_name='حفيد', gender='M', father=son)
        great_grandson = Person.objects.create(first_name='ابن_حفيد', gender='M', father=grandson)

        result = get_subtree_ids(root.id)

        self.assertEqual(result, {root.id, son.id, grandson.id, great_grandson.id})

    def test_uses_prebuilt_children_map(self):
        root = Person.objects.create(first_name='جد', gender='M')
        son = Person.objects.create(first_name='ابن', gender='M', father=root)
        prebuilt = {root.id: [son.id]}

        result = get_subtree_ids(root.id, children_map=prebuilt)

        self.assertEqual(result, {root.id, son.id})


class GetGenerationMapTests(TestCase):
    def test_single_root_returns_one_generation(self):
        root = Person.objects.create(first_name='جد', gender='M')

        result = get_generation_map(root.id)

        self.assertEqual(result, {1: [root.id]})

    def test_multi_generation_tree(self):
        root = Person.objects.create(first_name='جد', gender='M')
        son1 = Person.objects.create(first_name='ابن١', gender='M', father=root)
        son2 = Person.objects.create(first_name='ابن٢', gender='M', father=root)
        grandson = Person.objects.create(first_name='حفيد', gender='M', father=son1)

        result = get_generation_map(root.id)

        self.assertEqual(result[1], [root.id])
        self.assertCountEqual(result[2], [son1.id, son2.id])
        self.assertEqual(result[3], [grandson.id])
        self.assertEqual(len(result), 3)


class FindRelationshipTests(TestCase):
    """Labels describe person A relative to person B ("A is B's X"), with the
    possessive pronoun agreeing with B's gender. Maternal links add a second side."""

    def setUp(self):
        #            G (جد, M)
        #          /   |    \
        #        F1   F2    GM (جدة لأم, F, root)
        #        |   / | \        \
        #        K  S SB SA       (S.mother = GM)
        #       (K.mother = S)        SB has son C and daughter CD
        self.G = Person.objects.create(first_name='جد', gender='M')
        self.F1 = Person.objects.create(first_name='أب1', gender='M', father=self.G)
        self.F2 = Person.objects.create(first_name='أب2', gender='M', father=self.G)
        self.GM = Person.objects.create(first_name='جدةلأم', gender='F')
        self.K = Person.objects.create(first_name='خالد', gender='M', father=self.F1)
        self.S = Person.objects.create(first_name='سعاد', gender='F', father=self.F2, mother=self.GM)
        self.SB = Person.objects.create(first_name='خال', gender='M', father=self.F2)
        self.SA = Person.objects.create(first_name='خالة', gender='F', father=self.F2)
        self.C = Person.objects.create(first_name='ابنخال', gender='M', father=self.SB)
        self.CD = Person.objects.create(first_name='بنتخال', gender='F', father=self.SB)
        self.K.mother = self.S
        self.K.save()

    def _mat(self, a, b):
        r = find_relationship(a.id, b.id)['maternal']
        return r['label_ar'] if r else None

    def _pat(self, a, b):
        r = find_relationship(a.id, b.id)['paternal']
        return r['label_ar'] if r else None

    def test_father_son(self):
        self.assertEqual(self._pat(self.F1, self.K), 'أبوه')  # F1 is K's father
        self.assertEqual(self._pat(self.K, self.F1), 'ابنه')  # K is F1's son

    def test_pronoun_agrees_with_female_b(self):
        # The bug report: father of a daughter must read أبوها, not أبوه.
        self.assertEqual(self._pat(self.F2, self.S), 'أبوها')  # F2 is سعاد's father
        self.assertEqual(self._pat(self.S, self.F2), 'بنته')   # سعاد is F2's daughter

    def test_sibling_pronoun_agreement(self):
        # SON-side: K's gender drives أخو/أخت, the other person's gender drives ه/ها.
        self.assertEqual(self._pat(self.SB, self.SA), 'أخوها')  # SB is SA's brother
        self.assertEqual(self._pat(self.SA, self.SB), 'أخته')   # SA is SB's sister

    def test_purely_paternal_pair_has_no_maternal_side(self):
        self.assertIsNone(self._mat(self.K, self.F1))

    def test_mother_direct_link(self):
        self.assertEqual(self._mat(self.K, self.S), 'ابنها')  # K is سعاد's son

    def test_maternal_uncle_and_nephew(self):
        self.assertEqual(self._mat(self.SB, self.K), 'خاله')      # SB is K's maternal uncle
        self.assertEqual(self._mat(self.K, self.SB), 'ابن أخته')  # K is SB's sister's son

    def test_maternal_aunt_and_nephew(self):
        self.assertEqual(self._mat(self.SA, self.K), 'خالته')      # SA is K's maternal aunt
        self.assertEqual(self._mat(self.K, self.SA), 'ابن أختها')  # K is SA's sister's son

    def test_maternal_cousins(self):
        self.assertEqual(self._mat(self.C, self.K), 'ابن خاله')   # C is son of K's maternal uncle
        self.assertEqual(self._mat(self.CD, self.K), 'بنت خاله')  # CD is daughter of K's maternal uncle
        self.assertEqual(self._mat(self.K, self.C), 'ابن عمته')   # K is son of C's paternal aunt

    def test_maternal_grandmother(self):
        self.assertEqual(self._mat(self.GM, self.K), 'جدته')   # GM is K's maternal grandmother
        self.assertEqual(self._mat(self.K, self.GM), 'حفيدها')  # K is GM's grandson

    def test_both_sides_present(self):
        result = find_relationship(self.SB.id, self.K.id)
        self.assertEqual(result['paternal']['label_ar'], 'ابن عمه')  # paternal cousin
        self.assertEqual(result['maternal']['label_ar'], 'خاله')      # maternal uncle

    def test_path_edges_marks_maternal_hop(self):
        result = find_relationship(self.K.id, self.SB.id)['maternal']
        self.assertIn('M', result['path_edges'])

    def test_no_spurious_maternal_when_ancestor_has_mother(self):
        # خالد is بيان's father; خالد's own mother is أصيلة. The maternal side
        # must not climb past خالد to أصيلة and invent "بنت أخيه".
        aseela = Person.objects.create(first_name='أصيلة', gender='F')
        khalid = Person.objects.create(first_name='خالدأب', gender='M', mother=aseela)
        bayan = Person.objects.create(first_name='بيان', gender='F', father=khalid)
        result = find_relationship(khalid.id, bayan.id)
        self.assertEqual(result['paternal']['label_ar'], 'أبوها')  # he is her father
        self.assertIsNone(result['maternal'])                      # no bogus بنت أخيه

    def test_no_relationship_returns_both_none(self):
        stranger = Person.objects.create(first_name='غريب', gender='M')
        result = find_relationship(self.K.id, stranger.id)
        self.assertIsNone(result['paternal'])
        self.assertIsNone(result['maternal'])


class PersonModelIntegrationTests(TestCase):
    def test_get_subtree_ids_delegates_to_module(self):
        root = Person.objects.create(first_name='جد', gender='M')
        son = Person.objects.create(first_name='ابن', gender='M', father=root)
        grandson = Person.objects.create(first_name='حفيد', gender='M', father=son)

        result = set(root.get_subtree_ids())

        self.assertEqual(result, {root.id, son.id, grandson.id})
