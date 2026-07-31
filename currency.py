import os
import subprocess
from trytond.pool import PoolMeta, Pool
from .tools import ImporterModel
from trytond.transaction import Transaction
import trytond.config as config
from trytond import backend

class ImporterCurrency(ImporterModel):
    'Importer Currency'
    __name__ = 'importer.currency'

    @classmethod
    def importer_import(cls, records):
        env = os.environ.copy()
        env['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + 'trytond:proteus'
        env['TRYTOND_DATABASE_URI'] = config.get('database', 'uri',
            default='sqlite:///')
        command = ('python ./trytond/trytond/modules/currency/scripts/'
            'import_currencies.py -d %s' % Transaction().database.name)

        if backend.name == 'sqlite':
            Transaction().connection.commit()

        subprocess.check_call(command, shell=True, env=env)
        Transaction().connection.commit()

        Currency = Pool().get("currency.currency")
        return Currency.search([])


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'currency': {
                    'string': 'Currency',
                    'model': 'importer.currency',
                    'requires_records': False,
                    }
                })
        return methods
