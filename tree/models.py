from django.db import models


class Person(models.Model):
    GENDER_CHOICES = [('M', 'ذكر'), ('F', 'أنثى')]

    first_name = models.CharField('الاسم', max_length=100, db_index=True)
    gender = models.CharField('الجنس', max_length=1, choices=GENDER_CHOICES)
    birth_year = models.IntegerField('سنة الميلاد', null=True, blank=True)
    is_deceased = models.BooleanField('متوفى', default=False)
    death_year = models.IntegerField('سنة الوفاة', null=True, blank=True)
    phone = models.CharField('الهاتف', max_length=20, blank=True, default='')
    house_location = models.URLField('موقع المنزل', max_length=500, blank=True, default='')
    education = models.CharField('التعليم', max_length=255, blank=True, default='')
    occupation = models.CharField('المهنة', max_length=255, blank=True, default='')
    photo = models.ImageField('الصورة', upload_to='photos/', null=True, blank=True)
    father = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='children', verbose_name='الأب'
    )
    mother = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children_by_mother', verbose_name='الأم'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'شخص'
        verbose_name_plural = 'أشخاص'
        ordering = ['id']

    def __str__(self):
        return self.first_name

    @property
    def is_alive(self):
        return not self.is_deceased

    def get_subtree_ids(self):
        from .tree_utils import get_subtree_ids
        return list(get_subtree_ids(self.id))


class EditLog(models.Model):
    """Append-only audit trail of every field change made to a Person."""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='edit_logs', verbose_name='الشخص')
    field_name = models.CharField('الحقل', max_length=100)
    old_value = models.TextField('القيمة القديمة', blank=True, default='')
    new_value = models.TextField('القيمة الجديدة', blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سجل تعديل'
        verbose_name_plural = 'سجلات التعديل'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.person.first_name}: {self.field_name}'
