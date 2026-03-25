from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel


class ImporterSpanishBank(ImporterModel):
    'Importer Spanish Bank'
    __name__ = 'importer.spanish_bank'

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Bank = pool.get('bank')
        LoadBanks = pool.get('load.banks', type='wizard')

        session_id, _, _ = LoadBanks.create()
        LoadBanks.execute(session_id, {}, 'accept')

        return Bank.search([])


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'spanish_bank': {
                    'string': 'Spanish Banks',
                    'model': 'importer.spanish_bank',
                    'requires_records': False,
                    },
                })
        return methods
