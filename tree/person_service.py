from django.db import transaction

from .models import Person, EditLog
from .tree_utils import get_ancestors

YEAR_FIELDS = ('birth_year', 'death_year')


def update_person(person, changes):
    with transaction.atomic():
        logs = []
        for field, new_value in changes.items():
            old_value = getattr(person, field)

            if field in YEAR_FIELDS:
                if new_value != old_value:
                    logs.append(EditLog.objects.create(
                        person=person,
                        field_name=field,
                        old_value=str(old_value or ''),
                        new_value=str(new_value or ''),
                    ))
                    setattr(person, field, new_value)
            else:
                old_str = str(old_value or '')
                new_str = str(new_value or '')
                if new_str != old_str:
                    logs.append(EditLog.objects.create(
                        person=person,
                        field_name=field,
                        old_value=old_str,
                        new_value=new_str,
                    ))
                    setattr(person, field, new_value)

        person.save()
    return logs


def delete_person(person):
    if person.father is None:
        raise ValueError('لا يمكن حذف جذر الشجرة')
    if person.children.exists():
        raise ValueError('لا يمكن حذف شخص لديه أبناء')

    EditLog.objects.create(
        person=person.father,
        field_name='_deleted_child',
        old_value=person.first_name,
        new_value='',
    )
    person.delete()


def set_mother(person, mother):
    """Link (or unlink, when ``mother`` is None) a node's mother.

    The mother must be an existing female node and may not create a kinship
    cycle (i.e. ``person`` must not already be an ancestor of ``mother`` in the
    combined father+mother graph). Records the change in the edit log.
    """
    if mother is not None:
        if mother.gender != 'F':
            raise ValueError('الأم يجب أن تكون أنثى')
        if mother.id == person.id:
            raise ValueError('لا يمكن تعيين الشخص أمًا لنفسه')
        if person.id in get_ancestors(mother.id):
            raise ValueError('لا يمكن تعيين أحد الأبناء أمًا')

    old_name = person.mother.first_name if person.mother else ''
    new_name = mother.first_name if mother else ''
    if old_name == new_name and (person.mother_id == (mother.id if mother else None)):
        return  # no change

    EditLog.objects.create(
        person=person,
        field_name='mother',
        old_value=old_name,
        new_value=new_name,
    )
    person.mother = mother
    person.save()


def add_child(father, data):
    first_name = (data.get('first_name') or '').strip()
    gender = data.get('gender', 'M')

    if not first_name:
        raise ValueError('الاسم مطلوب')
    if father.gender == 'F':
        raise ValueError('لا يمكن إضافة أبناء تحت الإناث')

    child = Person.objects.create(
        first_name=first_name,
        gender=gender,
        father=father,
    )

    EditLog.objects.create(
        person=child,
        field_name='_created',
        old_value='',
        new_value=f'أضيف كـ {"ابن" if gender == "M" else "ابنة"} لـ {father.first_name}',
    )

    return child


def add_root(data):
    first_name = (data.get('first_name') or '').strip()
    if not first_name:
        raise ValueError('الاسم مطلوب')
    if Person.objects.filter(father__isnull=True).exists():
        raise ValueError('توجد بالفعل شخصية جذر في الشجرة')

    person = Person.objects.create(first_name=first_name, gender='M', father=None)
    EditLog.objects.create(
        person=person,
        field_name='_created',
        old_value='',
        new_value='أضيف كجذر الشجرة',
    )
    return person
