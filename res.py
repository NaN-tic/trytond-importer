from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta


class ImporterUser(ModelView):
    'Importer User'
    __name__ = 'importer.user'

    name = fields.Char('Name')
    login = fields.Char('Login')
    password = fields.Char('Password')
    signature = fields.Char('Signature')
    language_code = fields.Char('Language Code')
    email = fields.Char('Email')
    groups = fields.Char('Groups', help="Comma separated list of group names")
    roles = fields.Char('Roles', help="Comma separated list of role names")
    companies = fields.Char('Companies',
        help="Comma separated list of company names")
    company = fields.Char('Company')


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
                'user': {
                    'string': 'Users',
                    'model': 'importer.user',
                    'chunked': True,
                    },
                'role': {
                    'string': 'Roles',
                    'model': 'importer.role',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_user(cls, records, force=False):
        pool = Pool()
        User = pool.get('res.user')
        Group = pool.get('res.group')
        Language = pool.get('ir.lang')
        try:
            Role = pool.get('res.role')
            UserRole = pool.get('res.user.role')
        except KeyError:
            Role = None
            UserRole = None
        try:
            Company = pool.get('company.company')
        except KeyError:
            Company = None

        langs = Language.search([('translatable', '=', True)])
        langs = {x.code: x for x in langs}

        groups = Group.search([])
        groups = {x.name: x for x in groups}

        if Role:
            roles = Role.search([])
            roles = {x.name: x for x in roles}
        else:
            roles = {}

        if Company:
            companies = Company.search([])
            companies = {x.party.name: x for x in companies}
        else:
            companies = {}

        to_save = []
        for record in records:
            users = User.search([('login', '=', record.login)], limit=1)
            if users:
                user, = users
            else:
                user = User()
                user.login = record.login

            if record.name:
                user.name = record.name
            if record.password:
                user.password = record.password
            if record.signature:
                user.signature = record.signature
            if record.email:
                user.email = record.email

            if record.language_code:
                user.language = langs.get(record.language_code)

            if record.groups:
                groups_to_add = []
                for group in record.groups.split(','):
                    if group.strip() not in groups:
                        raise UserError(gettext('importer.msg_group_not_found',
                                group=group))
                    groups_to_add.append(groups[group])
                user.groups = groups_to_add

            if record.roles and Role:
                roles_to_add = []
                for role in record.roles.split(','):
                    if role.strip() not in roles:
                        raise UserError(gettext('importer.msg_role_not_found',
                                role=role))
                    roles_to_add.append(UserRole(role=roles[role]))
                user.roles = roles_to_add

            if Company:
                if record.companies:
                    companies_to_add = []
                    for company in record.companies.split(','):
                        if company.strip() not in companies:
                            raise UserError(gettext(
                                    'importer.msg_company_not_found',
                                    company=company))
                        companies_to_add.append(companies[company])
                    user.companies = companies_to_add

                if record.company:
                    if record.company.strip() not in companies:
                        raise UserError(gettext(
                                'importer.msg_company_not_found',
                                company=record.company))
                    user.company = companies[record.company]

            to_save.append(user)

        User.save(to_save)
        return to_save

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


