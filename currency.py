import os
import subprocess
from trytond.model import ModelView
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.config import config
from trytond import backend

class ImporterCurrency(ModelView):
    'Importer Currency'
    __name__ = 'importer.currency'


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'currency': {
                    'string': 'Currency',
                    'model': 'importer.currency',
                    'chunked': True,
                    'requires_records': False,
                    }
                })
        return methods

    @classmethod
    def import_currency(cls):
        env = os.environ.copy()
        env['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + 'trytond:proteus'
        env['TRYTOND_DATABASE_URI'] = config.get('database', 'uri',
            default='sqlite:///')
        command = ('python ./trytond/trytond/modules/currency/scripts/'
            'import_currencies.py -d %s' % Transaction().database.name)

        if backend.name == 'sqlite':
            # We commit the transaction to free the database
            # for the import script to work
            Transaction().connection.commit()

        subprocess.check_call(command, shell=True, env=env)

        # We commit the transaction to access to all the created currencies
        Transaction().connection.commit()

        Currency = Pool().get("currency.currency")
        return Currency.search([])
