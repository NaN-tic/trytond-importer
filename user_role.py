from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta


class ImporterRole(ModelView):
    'Importer Role'
    __name__ = 'importer.role'

    name = fields.Char('Name')
    groups = fields.Char('Groups', help="Comma separated list of group names")



class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'role': {
                    'string': 'Roles',
                    'model': 'importer.role',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_role(cls, records):
        pool = Pool()
        Group = pool.get('res.group')
        Role = pool.get('res.role')

        groups = Group.search([])
        groups = {x.name: x for x in groups}

        to_save = []
        for record in records:
            roles = Role.search([('name', '=', record.name)], limit=1)
            if roles:
                role, = roles
            else:
                role = Role()
                role.name = record.name

            if record.groups:
                groups_to_add = []
                for group in record.groups.split(','):
                    if group.strip() not in groups:
                        raise UserError(gettext('importer.msg_group_not_found',
                                group=group))
                    groups_to_add.append(groups[group])
                role.groups = groups_to_add

            to_save.append(role)

        Role.save(to_save)
        return to_save


