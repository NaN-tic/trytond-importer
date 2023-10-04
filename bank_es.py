from trytond.model import ModelView
from trytond.pool import PoolMeta, Pool


class ImporterSpanishBank(ModelView):
    'Importer Spanish Bank'
    __name__ = 'importer.spanish_bank'


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'spanish_bank': {
                    'string': 'Spanish Banks',
                    'model': 'importer.spanish_bank',
                    'chunked': True,
                    'requires_records': False,
                    },
                })
        return methods

    @classmethod
    def import_spanish_bank(cls):
        pool = Pool()
        Bank = pool.get('bank')
        LoadBanks = pool.get('load.banks', type='wizard')

        session_id, _, _ = LoadBanks.create()
        LoadBanks.execute(session_id, {}, 'accept')

        banks = Bank.search([])
        return banks
