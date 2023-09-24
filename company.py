from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterCompany(ModelView):
    'Importer Company'
    __name__ = 'importer.company'

    name = fields.Char("Name")
    currency = fields.Char("Currency")
    timezone = fields.Char("timezone")


class ImporterEmployee(ModelView):
    'Importer Employoee'
    __name__ = 'importer.employee'

    name = fields.Char('Name')
    company = fields.Char('Company')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    supervisor = fields.Char('Supervisor')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'company': {
                    'string': 'Company',
                    'model': 'importer.company',
                    'chunked': True,
                    },
                'employee': {
                    'string': 'Employee',
                    'model': 'importer.employee',
                    'chunked': True,
                    }
                })
        return methods

    @classmethod
    def import_company(cls, records):
        pool = Pool()

        Company = pool.get("company.company")
        Currency = pool.get("currency.currency")
        Party = pool.get("party.party")

        to_save = []
        for record in records:
            if not record.name:
                raise UserError(gettext('importer.msg_name_required'))

            companies = Company.search([('party.name', '=', record.name)],
                limit=1)
            if companies:
                company, = companies
            else:
                company = Company()
                parties = Party.search(["name", "=", record.name], limit=1)
                if parties:
                    party, = parties
                else:
                    party = Party()
                    party.name = record.name
                    party.save()
                company.party = party

            if record.currency:
                currencies = Currency.search([
                    ('code', '=', record.currency or 'EUR'),
                    ], limit=1)
                if not currencies:
                    raise UserError(gettext('importer.msg_currency_not_found',
                            currency=record.currency))
                company.currency, = currencies

            if record.timezone:
                company.timezone = record.timezone

            to_save.append(company)

        Company.save(to_save)
        return to_save

    @classmethod
    def import_employee(cls, records):
        pool = Pool()
        Company = pool.get("company.company")
        Employee = pool.get("company.employee")
        Party = pool.get("party.party")

        saved = []
        for record in records:
            if not record.name:
                raise UserError(gettext('importer.msg_name_required'))


            employees = Employee.search([('party.name', '=', record.name)],
                limit=1)
            if employees:
                employee, = companies
            else:
                employee = Employee()
                parties = Party.search(["name", "=", record.name], limit=1)
                if parties:
                    party, = parties
                else:
                    party = Party()
                    party.name = record.name
                    party.save()
                employee.party = party

            if record.company:
                companies = Company.search([('party.name', '=', record.company)],
                    limit=1)
                if not companies:
                    raise UserError(gettext('importer.msg_company_not_found',
                            company=record.company))
                employee.company, = companies

            if record.start_date:
                employee.start_date = record.start_date
            if record.end_date:
                employee.end_date = record.end_date
            if record.supervisor:
                supervisors = Employee.search([('party.name', '=', record.supervisor)],
                    limit=1)
                if not supervisors:
                    raise UserError(gettext('importer.msg_supervisor_not_found',
                            supervisor=record.supervisor))
                employee.supervisor, = supervisors

            # Save on each iteration so we can import supervisors in the same file
            employee.save()
            saved.append(employee)

        return saved
