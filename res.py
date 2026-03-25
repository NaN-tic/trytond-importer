from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from .tools import ImporterModel


class ImporterUser(ImporterModel):
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
        help="Pipe '|' separated list of company names")
    company = fields.Char('Company')
    employees = fields.Char('Employees',
        help="Comma separated list of employee names")
    employee = fields.Char('Employee')

    @classmethod
    def importer_import(cls, records):
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
            Employee = pool.get('company.employee')
        except KeyError:
            Company = None
            Employee = None

        langs = Language.search([('translatable', '=', True)])
        langs = {x.code: x for x in langs}

        groups = Group.search([])
        groups = {x.name: x for x in groups}
        admin_groups = list(User(1).groups)

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

        if Employee:
            employees = Employee.search([])
            employees = {x.party.name: x for x in employees}
        else:
            employees = {}

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
                record_groups = [x.strip() for x in record.groups.split(',')]
                if 'all' in record_groups:
                    groups_to_add = admin_groups
                else:
                    for group in record_groups:
                        if group.strip() not in groups:
                            raise UserError(gettext('importer.msg_group_not_found',
                                    name=group))
                        groups_to_add.append(groups[group])
                user.groups = groups_to_add

            if record.roles and Role:
                roles_to_add = []
                for role in [x.strip() for x in record.roles.split(',')]:
                    if role.strip() not in roles:
                        raise UserError(gettext('importer.msg_role_not_found',
                                name=role))
                    roles_to_add.append(UserRole(role=roles[role]))
                user.roles = roles_to_add

            if Company:
                if record.companies:
                    companies_to_add = []
                    for company in [x.strip() for x in record.companies.split('|')]:
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

            if Employee:
                if record.employees:
                    employees_to_add = []
                    for employee in [x.strip() for x in record.employees.split(',')]:
                        if employee.strip() not in employees:
                            raise UserError(gettext(
                                    'importer.msg_employee_not_found',
                                    employee=employee))
                        employees_to_add.append(employees[employee])
                    user.employees = employees_to_add

                if record.employee:
                    if record.employee.strip() not in employees:
                        raise UserError(gettext(
                                'importer.msg_employee_not_found',
                                employee=record.employee))
                    user.employee = employees[record.employee]

            to_save.append(user)

        User.save(to_save)
        return to_save


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'user': {
                    'string': 'Users',
                    'model': 'importer.user',
                    },
                })
        return methods
