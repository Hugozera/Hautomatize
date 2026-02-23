from django.test import TestCase

from core.forms import RoleForm
from core.permissions import all_permission_codes
from core.models import Role


class RoleFormTests(TestCase):
    def test_permissions_field_is_multiple_choice(self):
        form = RoleForm()
        self.assertIn('permissions', form.fields)
        field = form.fields['permissions']
        # it should be a MultipleChoiceField with checkbox widget
        from django.forms import MultipleChoiceField
        from django.forms.widgets import CheckboxSelectMultiple
        self.assertIsInstance(field, MultipleChoiceField)
        self.assertIsInstance(field.widget, CheckboxSelectMultiple)
        # choices should include all known codes
        codes = [c for c, _ in field.choices]
        for code in all_permission_codes():
            self.assertIn(code, codes)

    def test_form_saves_comma_separated_permissions(self):
        codes = all_permission_codes()
        selected = codes[:3]
        form = RoleForm(data={
            'name': 'TestRole',
            'codename': 'testrole',
            'descricao': 'foo',
            'permissions': selected,
            'ativo': True,
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        role = form.save()
        self.assertIsInstance(role, Role)
        self.assertEqual(role.permissions, ','.join(selected))

    def test_initial_permissions_from_instance(self):
        # create role manually
        role = Role.objects.create(name='R', codename='r', permissions='empresa.edit,download.manage', ativo=True)
        form = RoleForm(instance=role)
        self.assertEqual(set(form.initial['permissions']), {'empresa.edit', 'download.manage'})
