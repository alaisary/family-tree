import csv

from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import require_POST, require_GET

from .models import Person, EditLog
from .services import validate_photo


def healthz(request):
    """Liveness/readiness probe: 200 if the DB answers, 503 otherwise."""
    from django.db import connection
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'ok'})
    except Exception:
        return JsonResponse({'status': 'error'}, status=503)


# --- Tree View ---

def tree_view(request):
    return render(request, 'tree/tree.html', {
        'has_root': Person.objects.filter(father__isnull=True).exists(),
    })


@require_GET
@gzip_page
def tree_data(request):
    root = Person.objects.filter(father__isnull=True).first()
    if not root:
        return JsonResponse({'error': 'لا توجد بيانات'}, status=404)

    all_persons = list(Person.objects.all().values(
        'id', 'first_name', 'gender', 'birth_year', 'death_year', 'is_deceased',
        'father_id', 'photo'
    ))

    person_map = {p['id']: p for p in all_persons}
    children_map = {}
    for p in all_persons:
        if p['father_id'] is not None:
            children_map.setdefault(p['father_id'], []).append(p['id'])

    def build_node(person_id):
        p = person_map[person_id]
        photo_url = ''
        if p['photo']:
            # Serve a small 96x96 thumbnail per node, not the full original.
            # The tree's default mode renders a photo on every node, so originals
            # would mean hundreds of MB on a large tree over mobile data.
            try:
                from easy_thumbnails.files import get_thumbnailer
                photo_url = get_thumbnailer(p['photo'])['node'].url
            except Exception:
                from django.conf import settings
                photo_url = settings.MEDIA_URL + str(p['photo'])
        node = {
            'id': p['id'],
            'name': p['first_name'],
            'gender': p['gender'],
            'birth_year': p['birth_year'],
            'death_year': p['death_year'],
            'is_alive': not p['is_deceased'],
            'has_photo': bool(p['photo']),
            'photo_url': photo_url,
            'children': [],
        }
        for child_id in children_map.get(person_id, []):
            node['children'].append(build_node(child_id))
        return node

    tree = build_node(root.id)
    return JsonResponse({'tree': tree})


# --- Search ---

@require_GET
def search_persons(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return render(request, 'tree/partials/search_results.html', {'results': []})

    # Split into name tokens, dropping the Arabic lineage connectors so that
    # "عبدالله بن محمد" and "عبدالله محمد" both work.
    connectors = {'بن', 'بنت', 'ابن', 'ابنة'}
    tokens = [t for t in query.split() if t and t not in connectors]
    if not tokens:
        tokens = [query]

    # First token narrows to candidates by first name; the rest are matched
    # against the ancestor chain in Python.
    candidates = Person.objects.filter(first_name__icontains=tokens[0])
    gender_filter = request.GET.get('gender')
    if gender_filter in ('M', 'F'):
        candidates = candidates.filter(gender=gender_filter)
    candidates = candidates.select_related(
        'father', 'father__father', 'father__father__father',
        'father__father__father__father',
    )[:200]

    results = []
    for p in candidates:
        # Build the lineage chain [self, father, grandfather, ...].
        chain_names = [p.first_name]
        ancestor = p.father
        depth = 0
        while ancestor and depth < 8:
            chain_names.append(ancestor.first_name)
            ancestor = ancestor.father
            depth += 1

        # Each remaining token must appear, in order, further up the chain.
        idx = 0
        matched = True
        for token in tokens:
            found_at = next((i for i in range(idx, len(chain_names)) if token in chain_names[i]), None)
            if found_at is None:
                matched = False
                break
            idx = found_at + 1
        if not matched:
            continue

        lineage_parts = chain_names[:4]
        if p.gender == 'F' and len(lineage_parts) > 1:
            display_name = lineage_parts[0] + ' بنت ' + ' بن '.join(lineage_parts[1:])
        else:
            display_name = ' بن '.join(lineage_parts)

        results.append({
            'id': p.id,
            'display_name': display_name,
            'is_alive': not p.is_deceased,
            'gender': p.gender,
        })
        if len(results) >= 20:
            break

    return render(request, 'tree/partials/search_results.html', {'results': results, 'query': query})


@require_GET
def find_relationship(request):
    try:
        person_a = int(request.GET.get('a', 0))
        person_b = int(request.GET.get('b', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'معرّفات غير صالحة'}, status=400)

    if not person_a or not person_b:
        return JsonResponse({'error': 'يجب تحديد شخصين'}, status=400)

    from .tree_utils import find_relationship as compute_relationship
    result = compute_relationship(person_a, person_b)
    if result['paternal'] is None and result['maternal'] is None:
        return JsonResponse({'error': 'لا توجد صلة قرابة'}, status=404)

    return JsonResponse(result)


# --- Node Detail ---

def _render_person_detail(request, person_id):
    person = get_object_or_404(
        Person.objects.select_related('father', 'mother'),
        id=person_id
    )
    children = Person.objects.filter(father=person).order_by('gender', 'id')
    return render(request, 'tree/partials/person_detail.html', {
        'person': person,
        'children': children,
        'can_add_child': person.gender == 'M',
        'can_delete': not person.children.exists(),
    })


@require_GET
def person_detail(request, person_id):
    return _render_person_detail(request, person_id)


# --- Edit Person ---

@require_GET
def person_edit_form(request, person_id):
    person = get_object_or_404(Person, id=person_id)
    return render(request, 'tree/partials/person_edit_form.html', {'person': person})


@require_POST
def person_update(request, person_id):
    from .person_service import update_person

    person = get_object_or_404(Person, id=person_id)

    # Validate the upload before mutating anything, so a bad file can't half-apply.
    if 'photo' in request.FILES:
        try:
            validate_photo(request.FILES['photo'])
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)

    editable_fields = ['first_name', 'birth_year', 'phone',
                       'house_location', 'education', 'occupation']

    changes = {}
    for field in editable_fields:
        new_value = request.POST.get(field, '').strip()
        if field == 'birth_year':
            new_value = int(new_value) if new_value else None
        changes[field] = new_value

    # Deceased status is an explicit flag; the death year is optional detail.
    # The checkbox is authoritative — unchecking "deceased" clears the death year
    # (a living person can't have one).
    is_deceased = request.POST.get('is_deceased') in ('on', '1', 'true')
    death_year = request.POST.get('death_year', '').strip()
    death_year = int(death_year) if death_year and is_deceased else None
    changes['is_deceased'] = is_deceased
    changes['death_year'] = death_year

    try:
        update_person(person, changes)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    if 'photo' in request.FILES:
        old_photo = str(person.photo) if person.photo else ''
        person.photo = request.FILES['photo']
        EditLog.objects.create(
            person=person,
            field_name='photo',
            old_value=old_photo,
            new_value='uploaded',
        )
        person.save()

    return _render_person_detail(request, person_id)


# --- Add Child / Root ---

@require_POST
def add_child(request, person_id):
    from .person_service import add_child as svc_add_child

    parent = get_object_or_404(Person, id=person_id)
    data = {
        'first_name': request.POST.get('first_name', ''),
        'gender': request.POST.get('gender', 'M'),
    }

    try:
        child = svc_add_child(parent, data)
    except ValueError as e:
        if 'الإناث' in str(e):
            return HttpResponseForbidden(str(e))
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({
        'success': True,
        'person_id': child.id,
        'message': f'تمت إضافة {child.first_name}',
    })


@require_POST
def add_root(request):
    from .person_service import add_root as svc_add_root

    try:
        person = svc_add_root({'first_name': request.POST.get('first_name', '')})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({
        'success': True,
        'person_id': person.id,
        'message': f'تمت إضافة {person.first_name}',
    })


# --- Set Mother ---

@require_POST
def set_mother(request, person_id):
    from .person_service import set_mother as svc_set_mother

    person = get_object_or_404(Person, id=person_id)
    mother_id = request.POST.get('mother_id', '').strip()
    apply_siblings = request.POST.get('apply_siblings') == '1'

    mother = None
    if mother_id:
        mother = get_object_or_404(Person, id=mother_id)

    try:
        svc_set_mother(person, mother)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    # Siblings share the father (the tree is patrilineal). Offer to apply the
    # same mother to siblings who don't have one yet — never overwriting a
    # sibling who already has a (possibly different) mother, so half-siblings
    # from another wife stay correct.
    eligible = []
    if mother is not None and person.father_id:
        eligible = list(
            Person.objects.filter(
                father_id=person.father_id, mother__isnull=True,
            ).exclude(id=person.id)
        )

    if apply_siblings and eligible:
        for sib in eligible:
            try:
                svc_set_mother(sib, mother)
            except ValueError:
                continue  # skip any sibling that would violate a guard
        eligible = []  # applied — nothing left to offer

    resp = _render_person_detail(request, person_id)
    resp['X-Eligible-Siblings'] = str(len(eligible))
    return resp


# --- Delete / Move ---

@require_POST
def delete_person(request, person_id):
    from .person_service import delete_person as svc_delete

    person = get_object_or_404(Person, id=person_id)
    name = person.first_name

    try:
        svc_delete(person)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'success': True, 'message': f'تم حذف {name}'})


@require_POST
def move_person(request, person_id):
    person = get_object_or_404(Person, id=person_id)

    if person.father is None:
        return JsonResponse({'error': 'لا يمكن نقل جذر الشجرة'}, status=400)

    new_father_id = request.POST.get('new_father_id')
    if not new_father_id:
        return JsonResponse({'error': 'يجب تحديد الأب الجديد'}, status=400)

    new_father = get_object_or_404(Person, id=new_father_id)

    if new_father.gender == 'F':
        return JsonResponse({'error': 'لا يمكن النقل تحت أنثى'}, status=400)

    descendant_ids = person.get_subtree_ids()
    if new_father.id in descendant_ids:
        return JsonResponse({'error': 'لا يمكن النقل إلى أحد الأحفاد'}, status=400)

    old_father = person.father
    EditLog.objects.create(
        person=person,
        field_name='father',
        old_value=old_father.first_name if old_father else '',
        new_value=new_father.first_name,
    )

    person.father = new_father
    person.save()

    return JsonResponse({
        'success': True,
        'message': f'تم نقل {person.first_name} إلى {new_father.first_name}',
    })


# --- Edit Log ---

@require_GET
def person_edit_log(request, person_id):
    person = get_object_or_404(Person, id=person_id)
    logs = EditLog.objects.filter(person=person).order_by('-created_at')[:50]
    return render(request, 'tree/partials/edit_log.html', {'person': person, 'logs': logs})


# --- Stats & Export ---

@require_GET
def branch_stats(request, person_id):
    from .tree_utils import get_subtree_ids, build_children_map, get_generation_map

    person = get_object_or_404(Person, id=person_id)
    children_map = build_children_map()
    subtree_ids = get_subtree_ids(person_id, children_map)
    members = Person.objects.filter(id__in=subtree_ids)

    total = members.count()
    males = members.filter(gender='M').count()
    females = members.filter(gender='F').count()
    alive = members.filter(death_year__isnull=True).count()
    deceased = members.filter(death_year__isnull=False).count()
    has_phone = members.exclude(phone='').count()
    has_photo = members.filter(photo__isnull=False).exclude(photo='').count()
    has_education = members.exclude(education='').count()
    has_occupation = members.exclude(occupation='').count()

    gen_map = get_generation_map(person_id, children_map)
    depth = max(gen_map.keys()) if gen_map else 0

    return JsonResponse({
        'person_id': person_id,
        'person_name': person.first_name,
        'total': total,
        'males': males,
        'females': females,
        'alive': alive,
        'deceased': deceased,
        'depth': depth,
        'has_phone': has_phone,
        'has_photo': has_photo,
        'has_education': has_education,
        'has_occupation': has_occupation,
        'phone_pct': round(has_phone / total * 100) if total else 0,
        'photo_pct': round(has_photo / total * 100) if total else 0,
        'education_pct': round(has_education / total * 100) if total else 0,
        'occupation_pct': round(has_occupation / total * 100) if total else 0,
    })


@require_GET
def branch_tree(request, person_id):
    from .tree_utils import build_children_map
    person = get_object_or_404(Person, id=person_id)
    all_persons = {p['id']: p for p in Person.objects.all().values('id', 'first_name', 'gender', 'father_id', 'death_year')}
    children_map = build_children_map()

    def build_node(pid):
        p = all_persons[pid]
        return {
            'id': p['id'],
            'name': p['first_name'],
            'gender': p['gender'],
            'alive': p['death_year'] is None,
            'children': [build_node(cid) for cid in children_map.get(pid, [])],
        }

    return JsonResponse(build_node(person_id))


@require_GET
def tree_stats(request):
    from .stats import get_aggregate_stats
    from .tree_utils import get_generation_map

    stats = get_aggregate_stats()

    root = Person.objects.filter(father__isnull=True).first()
    generations = 0
    if root:
        gen_map = get_generation_map(root.id)
        generations = max(gen_map.keys()) if gen_map else 0

    return JsonResponse({**stats, 'generations': generations})


@require_GET
def export_csv(request):
    from .tree_utils import get_generation_map

    persons = Person.objects.select_related('father').order_by('id')

    q = request.GET.get('q', '').strip()
    gender = request.GET.get('gender', '').strip()
    status = request.GET.get('status', '').strip()
    has_phone = request.GET.get('has_phone', '').strip()
    has_photo = request.GET.get('has_photo', '').strip()
    gen = request.GET.get('gen', '').strip()
    branch_id = request.GET.get('branch', '').strip()

    if q:
        persons = persons.filter(first_name__icontains=q)
    if gender in ('M', 'F'):
        persons = persons.filter(gender=gender)
    if status == 'alive':
        persons = persons.filter(death_year__isnull=True)
    elif status == 'deceased':
        persons = persons.filter(death_year__isnull=False)
    if has_phone == 'yes':
        persons = persons.exclude(phone='')
    elif has_phone == 'no':
        persons = persons.filter(phone='')
    if has_photo == 'yes':
        persons = persons.filter(photo__isnull=False).exclude(photo='')
    elif has_photo == 'no':
        persons = persons.filter(Q(photo__isnull=True) | Q(photo=''))
    if gen:
        try:
            root = Person.objects.filter(father__isnull=True).first()
            if root:
                gen_map = get_generation_map(root.id)
                gen_person_ids = gen_map.get(int(gen), [])
                persons = persons.filter(id__in=gen_person_ids)
        except ValueError:
            pass
    if branch_id:
        try:
            from .tree_utils import get_subtree_ids
            subtree = get_subtree_ids(int(branch_id))
            persons = persons.filter(id__in=subtree)
        except (ValueError, Person.DoesNotExist):
            pass

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="family_tree.csv"'
    response.write('﻿')

    writer = csv.writer(response)
    writer.writerow([
        'الرقم', 'الاسم', 'الجنس', 'سنة الميلاد', 'سنة الوفاة',
        'اسم الأب', 'الهاتف', 'التعليم', 'المهنة',
    ])

    for p in persons:
        writer.writerow([
            p.id,
            p.first_name,
            'ذكر' if p.gender == 'M' else 'أنثى',
            p.birth_year or '',
            p.death_year or '',
            p.father.first_name if p.father else '',
            p.phone,
            p.education,
            p.occupation,
        ])

    return response


# --- Delete Photo ---

@require_POST
def delete_photo(request, person_id):
    person = get_object_or_404(Person, id=person_id)

    if person.photo:
        person.photo.delete(save=False)
        EditLog.objects.create(
            person=person,
            field_name='photo',
            old_value='deleted',
            new_value='',
        )
        person.photo = None
        person.save()

    return _render_person_detail(request, person_id)
