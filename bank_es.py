from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterSpanishBank(ModelView):
    'Importer Spanish Bank'
    __name__ = 'importer.spanish_bank'
    name = fields.Char('Name')


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
                    },
                })
        return methods

    @classmethod
    def import_spanish_bank(cls, records):
        pool = Pool()
        LoadBanks = pool.get('load.banks', type='wizard')

        session_id, _, _ = LoadBanks.create()
        LoadBanks.execute(session_id, {}, 'accept')
        return []
