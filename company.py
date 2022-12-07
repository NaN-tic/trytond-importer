from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from stdnum import get_cc_module
from trytond.exceptions import UserError
from trytond.i18n import gettext

class ImporterCompany(ModelView):
    'Importer Company'
    __name__ = 'importer.company'

    name = fields.Char("Name")
    party_code = fields.Char("Party code")
    party_name = fields.Char("Party name")
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
            company = Company()

            if record.party_code:
                company.party = Party.search(["code", "=", record.party_code])[0]
            else:
                company.party = Party.search(["name", "=", record.party_name])[0]

            if not record.currency:
                eur = Currency.search(["code","=","EUR"])
                if len(eur) == 0:
                    return []
                company.currency = eur[0]
            else:
                company.currency = Currency.search(["code", "=", record.currency])[0].id

            if not record.timezone:
                company.timezone = "Europe/Madrid"
            else:
                company.timezone = record.timezone

            company.save()
            to_save.append(company)

        return to_save