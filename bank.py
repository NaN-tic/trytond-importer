from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterBank(ImporterModel):
    'Importer Bank'
    __name__ = 'importer.bank'
    name = fields.Char('Name')
    bic = fields.Char('BIC')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Bank = pool.get('bank')

        to_save = []
        for record in records:
            if not record.name:
                raise UserError(gettext('importer.msg_bank_name_required'))
            banks = Bank.search([('party.name', '=', record.name)], limit=1)
            if banks:
                bank, = banks
            else:
                parties = Party.search([('name', '=', record.name)], limit=1)
                if parties:
                    party, = parties
                else:
                    party = Party()
                    party.name = record.name
                    party.save()
                bank = Bank()
                bank.party = party

            bank.bic = record.bic
            to_save.append(bank)

        Bank.save(to_save)
        return to_save


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'bank': {
                    'string': 'Banks',
                    'model': 'importer.bank',
                    },
                })
        return methods
