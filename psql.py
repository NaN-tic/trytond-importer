from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
import psycopg2
import pathlib
import os

class Importer(metaclass=PoolMeta):
    'Importer'
    __name__ = 'importer'

    @classmethod
    def __setup__(cls):
        super(Importer, cls).__setup__()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        queries_dir = os.path.join(script_dir, "queries")
        items = [(f, f)for f in os.listdir(queries_dir) if f.endswith('.sql')]
        for item in items:
            cls.sql_data.selection.append(item)

        cls.sql_source.selection.append(('psql', 'PSQL'))

    def get_url_file(self):

        return os.path.join(pathlib.Path(__file__).parent.resolve(),
            'queries', self.sql_data)

    def check_connection_psql(self):
        try:
            psycopg2.connect(database = self.database, host=self.server,
                user=self.user, password=self.password, port=5432)
        except Exception as e:
            print(e)
            raise UserError(gettext('importer.msg_invalid_connection'))
        raise UserError(gettext('importer.msg_successful_connecion'))

    def get_connection_psql(self, fail=True):
        try:
            conn = psycopg2.connect(database = self.database, host=self.server,
                user=self.user, password=self.password, port=5432)
        except:
            if fail:
                raise UserError(gettext('importer.msg_invalid_connection'))
            else:
                return None
        return conn