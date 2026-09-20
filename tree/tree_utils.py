from collections import deque

from .models import Person


def build_parents_map(queryset=None):
    """Map person_id -> (father_id, mother_id) for the whole tree."""
    if queryset is None:
        queryset = Person.objects.all()
    return {
        pid: (fid, mid)
        for pid, fid, mid in queryset.values_list('id', 'father_id', 'mother_id')
    }


def get_ancestors(person_id, parents_map=None):
    """BFS over both parent edges (father + mother).

    Returns {ancestor_id: (depth, edges, path)} where ``edges[i]`` is the link
    ('F' father / 'M' mother) from ``path[i]`` up to ``path[i+1]``. The shortest
    (and, on ties, the most paternal) path to each ancestor wins, because the
    queue expands the father edge before the mother edge and the first visit of
    a node is kept. ``person_id`` itself is included at depth 0.
    """
    if parents_map is None:
        parents_map = build_parents_map()
    best = {}
    queue = deque([(person_id, 0, (), (person_id,))])
    while queue:
        current, depth, edges, path = queue.popleft()
        if current in best:
            continue
        best[current] = (depth, edges, path)
        father_id, mother_id = parents_map.get(current, (None, None))
        if father_id is not None:
            queue.append((father_id, depth + 1, edges + ('F',), path + (father_id,)))
        if mother_id is not None:
            queue.append((mother_id, depth + 1, edges + ('M',), path + (mother_id,)))
    return best


def build_children_map(queryset=None):
    if queryset is None:
        queryset = Person.objects.all()
    children_map = {}
    for pid, fid in queryset.values_list('id', 'father_id'):
        if fid is not None:
            children_map.setdefault(fid, []).append(pid)
    return children_map


def get_subtree_ids(person_id, children_map=None):
    if children_map is None:
        children_map = build_children_map()
    ids = set()
    queue = [person_id]
    while queue:
        current = queue.pop(0)
        ids.add(current)
        queue.extend(children_map.get(current, []))
    return ids


def get_generation_map(root_id, children_map=None):
    if children_map is None:
        children_map = build_children_map()
    generations = {}
    queue = [(root_id, 1)]
    visited = set()
    while queue:
        current, depth = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        generations.setdefault(depth, []).append(current)
        for child_id in children_map.get(current, []):
            queue.append((child_id, depth + 1))
    return generations


def get_ancestor_chain(person_id, father_map=None):
    if father_map is None:
        father_map = {pid: fid for pid, fid in Person.objects.values_list('id', 'father_id')}
    chain = []
    current = person_id
    while current is not None:
        chain.append(current)
        current = father_map.get(current)
    return chain


def find_relationship(person_a_id, person_b_id):
    """Relationship between two people, on both the paternal and maternal sides.

    Returns ``{'paternal': result|None, 'maternal': result|None}``:
      * ``paternal`` walks only father chains (the classic patrilineal answer).
      * ``maternal`` is the closest connection over the full father+mother graph
        whose linking path uses at least one mother edge.
    Both ``None`` means no kinship at all.
    """
    parents_map = build_parents_map()
    father_map = {pid: fid for pid, (fid, _mid) in parents_map.items()}
    genders = dict(Person.objects.values_list('id', 'gender'))
    gender_a = genders.get(person_a_id, 'M')
    gender_b = genders.get(person_b_id, 'M')

    paternal = _relationship_paternal(person_a_id, person_b_id, father_map, gender_a, gender_b)
    maternal = _relationship_maternal(person_a_id, person_b_id, parents_map, gender_a, gender_b)

    return {'paternal': paternal, 'maternal': maternal}


def _build_result(person_a_id, person_b_id, lca_id, depth_a, depth_b,
                  path_ids, path_edges, label_ar):
    names = dict(Person.objects.filter(id__in=path_ids).values_list('id', 'first_name'))
    return {
        'person_a': person_a_id,
        'person_b': person_b_id,
        'lca_id': lca_id,
        'lca_name': names.get(lca_id, '?'),
        'depth_a': depth_a,
        'depth_b': depth_b,
        'label_ar': label_ar,
        'path_ids': path_ids,
        'path_names': [names.get(pid, '?') for pid in path_ids],
        'path_edges': list(path_edges),
    }


def _relationship_paternal(person_a_id, person_b_id, father_map, gender_a, gender_b):
    chain_a = get_ancestor_chain(person_a_id, father_map)
    chain_b = get_ancestor_chain(person_b_id, father_map)

    set_b = set(chain_b)
    lca_id = next((pid for pid in chain_a if pid in set_b), None)
    if lca_id is None:
        return None

    depth_a = chain_a.index(lca_id)
    depth_b = chain_b.index(lca_id)

    path_ids = list(reversed(chain_a[:depth_a + 1])) + chain_b[:depth_b][::-1]
    seen = set()
    unique_path = []
    for pid in path_ids:
        if pid not in seen:
            seen.add(pid)
            unique_path.append(pid)
    path_edges = ['F'] * (len(unique_path) - 1)

    label_ar = _relationship_label(
        depth_a, depth_b, ('F',) * depth_a, ('F',) * depth_b, gender_a, gender_b)
    return _build_result(person_a_id, person_b_id, lca_id, depth_a, depth_b,
                         unique_path, path_edges, label_ar)


def _relationship_maternal(person_a_id, person_b_id, parents_map, gender_a, gender_b):
    anc_a = get_ancestors(person_a_id, parents_map)
    anc_b = get_ancestors(person_b_id, parents_map)

    best = None  # (depth_a + depth_b, lca_id, depth_a, depth_b, edges_a, edges_b, path)
    for lca_id, (depth_a, edges_a, path_a) in anc_a.items():
        if lca_id not in anc_b:
            continue
        depth_b, edges_b, path_b = anc_b[lca_id]
        if 'M' not in edges_a and 'M' not in edges_b:
            continue  # purely paternal — already covered by the paternal result
        if set(path_a) & set(path_b) != {lca_id}:
            continue  # paths overlap below this node → not a true LCA
        total = depth_a + depth_b
        if best is None or total < best[0]:
            best = (total, lca_id, depth_a, depth_b, edges_a, edges_b, path_a, path_b)

    if best is None:
        return None

    _total, lca_id, depth_a, depth_b, edges_a, edges_b, path_a, path_b = best

    # A -> LCA -> B, dropping the duplicated LCA in the middle
    path_ids = list(path_a) + list(reversed(path_b[:-1]))
    path_edges = list(edges_a) + list(reversed(edges_b))

    label_ar = _relationship_label(depth_a, depth_b, edges_a, edges_b, gender_a, gender_b)
    return _build_result(person_a_id, person_b_id, lca_id, depth_a, depth_b,
                         path_ids, path_edges, label_ar)


# ---------------------------------------------------------------------------
# Arabic kinship labelling.
#
# Convention: the label describes PERSON A relative to PERSON B — "A is B's X" —
# so every possessive pronoun agrees with B's gender ('ه' for a male B, 'ها' for
# a female B), and the relationship noun reflects A's own gender. Works for both
# father-only and mixed maternal paths: ``edges_a`` / ``edges_b`` are tuples of
# 'F' (father link) / 'M' (mother link) from each endpoint up to the common
# ancestor, so عم/عمة (paternal) vs خال/خالة (maternal) follows the link type.
# ---------------------------------------------------------------------------


def _relationship_label(depth_a, depth_b, edges_a, edges_b, gender_a, gender_b):
    pron = 'ه' if gender_b == 'M' else 'ها'  # possessive referring to person B

    if depth_a == 0 and depth_b == 0:
        return 'نفس الشخص'

    # A is an ancestor of B (B climbs edges_b up to A).
    if depth_a == 0:
        return _ancestor_label(edges_b, pron)
    # A is a descendant of B (A climbs edges_a up to B).
    if depth_b == 0:
        return _descendant_label(depth_a, gender_a, pron)

    # A is B's sibling.
    if depth_a == 1 and depth_b == 1:
        return ('أخو' + pron) if gender_a == 'M' else ('أخت' + pron)

    # depth_b == 1: A descends from B's sibling → A is B's nephew/niece line.
    if depth_b == 1:
        sib_gender = 'M' if edges_a[depth_a - 2] == 'F' else 'F'
        return _desc_prefix(depth_a - 1, gender_a) + ' ' + _sibling_genitive(sib_gender, pron)

    # depth_a == 1: A is the sibling of one of B's ancestors → A is B's uncle/aunt.
    if depth_a == 1:
        return _uncle_label(edges_b, depth_b, gender_a, pron)

    # Both ≥ 2: A descends from the sibling of one of B's ancestors → cousin line.
    sa_gender = 'M' if edges_a[depth_a - 2] == 'F' else 'F'
    return _desc_prefix(depth_a - 1, gender_a) + ' ' + _uncle_label(edges_b, depth_b, sa_gender, pron)


def _ancestor_label(edges, pron):
    """A is B's ancestor; ``edges`` = B → … → A. Nominative ('A is B's <father>')."""
    link = edges[-1]
    if len(edges) == 1:
        return ('أبو' + pron) if link == 'F' else ('أم' + pron)        # أبوه/أبوها/أمه/أمها
    if len(edges) == 2 and edges[0] == link:
        return ('جد' + pron) if link == 'F' else ('جدت' + pron)        # جده/جدها/جدته/جدتها
    if len(edges) == 2:
        # mixed grandparent: أم أبيه (paternal grandmother) / أبو أمه (maternal grandfather)
        head = 'أبو' if link == 'F' else 'أم'
        return head + ' ' + _anc_genitive(edges[:-1], pron)
    # depth ≥ 3: A is the grandfather/grandmother of B's ancestor two levels down,
    # e.g. 'جد أبيه' (grandfather of his father), 'جد أمها' (grandfather of her mother).
    grand = 'جد' if link == 'F' else 'جدة'
    return grand + ' ' + _anc_genitive(edges[:-2], pron)


def _anc_genitive(edges, pron):
    """Genitive form of an ancestor of B (appears after another noun: '… of B')."""
    link = edges[-1]
    if len(edges) == 1:
        return ('أبي' + pron) if link == 'F' else ('أم' + pron)        # أبيه/أبيها/أمه/أمها
    if len(edges) == 2 and edges[0] == link:
        return ('جد' + pron) if link == 'F' else ('جدت' + pron)        # جده/جدها/جدته/جدتها
    head = 'أبي' if link == 'F' else 'أم'
    return head + ' ' + _anc_genitive(edges[:-1], pron)


def _descendant_label(hops, gender_a, pron):
    """A is B's descendant, ``hops`` generations down; noun by A's gender."""
    if hops == 1:
        return ('ابن' if gender_a == 'M' else 'بنت') + pron
    if hops == 2:
        return ('حفيد' if gender_a == 'M' else 'حفيدة') + pron
    if hops == 3:
        return ('ابن' if gender_a == 'M' else 'بنت') + ' حفيد' + pron
    if hops == 4:
        return ('حفيد' if gender_a == 'M' else 'حفيدة') + ' حفيد' + pron
    return ('ابن' if gender_a == 'M' else 'بنت') + ' حفيد حفيد' + pron


def _desc_prefix(hops, gender_a):
    """Leading descendant noun (no pronoun); only the outermost reflects gender."""
    if hops == 1:
        return 'ابن' if gender_a == 'M' else 'بنت'
    if hops == 2:
        return 'حفيد' if gender_a == 'M' else 'حفيدة'
    if hops == 3:
        return ('ابن' if gender_a == 'M' else 'بنت') + ' حفيد'
    if hops == 4:
        return ('حفيد' if gender_a == 'M' else 'حفيدة') + ' حفيد'
    return ('ابن' if gender_a == 'M' else 'بنت') + ' حفيد حفيد'


def _sibling_genitive(sib_gender, pron):
    """B's sibling, genitive: أخيه/أخيها (brother) or أخته/أختها (sister)."""
    return ('أخي' + pron) if sib_gender == 'M' else ('أخت' + pron)


def _uncle_label(edges_b, depth_b, uncle_gender, pron):
    """The عم/عمة/خال/خالة that A represents toward B.

    عم/عمة (paternal) when B reaches the branching ancestor through a father
    link, خال/خالة (maternal) through a mother link (``edges_b[depth_b - 2]``).
    ``uncle_gender`` is A's gender in the uncle case, or the cousin's parent's
    gender in the cousin case.
    """
    link_b = edges_b[depth_b - 2]
    if link_b == 'F':
        base = 'عم' if uncle_gender == 'M' else 'عمة'
    else:
        base = 'خال' if uncle_gender == 'M' else 'خالة'

    if depth_b == 2:
        # Direct uncle/aunt of B → attach the possessive pronoun.
        if base.endswith('ة'):
            return base[:-1] + 'ت' + pron       # عمة→عمته/عمتها, خالة→خالته/خالتها
        return base + pron                       # عم→عمه/عمها, خال→خاله/خالها
    # Uncle/aunt of one of B's ancestors → 'عم <ancestor of B>'.
    return base + ' ' + _anc_genitive(edges_b[:depth_b - 2], pron)
