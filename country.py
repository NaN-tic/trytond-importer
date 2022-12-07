import os
import subprocess
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from stdnum import get_cc_module
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.config import config

class ImporterCountry(ModelView):
    'Importer Country'
    __name__ = 'importer.country'

    name = fields.Char("name")

class ImporterPostalCodes(ModelView):
    'Importer Postal Codes'
    __name__ = 'importer.country.postal_codes'

    name = fields.Char("name")

class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'country': {
                    'string': 'Country',
                    'model': 'importer.country',
                    'chunked': True,
                    },
                'spanish_postal_codes': {
                    'string': 'Postal codes',
                    'model': 'importer.country.postal_codes',
                    'chunked': True,
                    },
                })
        return methods
        
    @classmethod
    def import_country(cls, records):
        env = os.environ.copy()
        env['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + 'trytond:proteus'
        env['TRYTOND_DATABASE_URI'] = config.get('database', 'uri', default='sqlite:///')
        command = ('python ./trytond/trytond/modules/country/scripts/'
            'import_countries.py -d %s' % Transaction().database.name)

        subprocess.check_call(command, shell=True, env=env)

        # We commit the transaction to access to all the created countries
        Transaction().connection.commit()

        Currency = Pool().get("country.country")
        return Currency.search([])

    def import_spanish_postal_codes(cls, records):
        env = os.environ.copy()
        env['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + 'trytond:proteus'
        env['TRYTOND_DATABASE_URI'] = config.get('database', 'uri', default='sqlite:///')
        command = ('python ./trytond/trytond/modules/country/scripts/'
            'import_postal_codes.py -d %s ES' % Transaction().database.name)

        subprocess.check_call(command, shell=True, env=env)

        # We commit the transaction to access to all the created postal codes
        Transaction().connection.commit()

        Currency = Pool().get("country.postal_code")
        return Currency.search([])