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
