from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from .tools import ImporterModel, Cache, Setup


class ImporterMeta(ImporterModel):
    'Importer Meta'
    __name__ = 'importer.meta'

    name = fields.Char('Name')
    method = fields.Char('Method')
    language = fields.Char('Language')
    data_source = fields.Char('Data Source')
    has_header = fields.Boolean('Has Header')
    use_header = fields.Boolean('Use Header')
    on_error = fields.Char('On Error')
    text_data = fields.Text('Text')
    binary_data = fields.Binary('Binary')
    url_data = fields.Char('URL')
    sql_source = fields.Char('SQL Source')
    server = fields.Char('Server')
    user = fields.Char('User')
    password = fields.Char('Password')
    database = fields.Char('Database')
    schema = fields.Char('Schema')
    where = fields.Char('Where')
    column_field = fields.Char('Column Field')
    column_name = fields.Char('Column Name')
    column_value = fields.Char('Column Value')
    column_format = fields.Char('Column Format')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.importers = Cache('importer', 'name')
        cache.languages = Cache('ir.lang', 'code')

    def importer_header(self, importing=True):
        return (self.name,)

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Importer = pool.get('importer')

        super().importer_import(records)
        setup = Setup.get()
        cache = setup.cache

        importers = []
        columns_to_save = []
        previous_header = None
        for record in records:
            setup.current_record = record
            header = cls.importer_header(record)
            if any(header) and header != previous_header:
                previous_header = header

                importer = cache.importers.get(record.name)
                if not importer:
                    values = Importer.default_get(
                        list(Importer._fields.keys()), with_rec_name=False)
                    importer = Importer(**values)
                    cache.importers[record.name] = importer
                record.importer_assign(importer)
                importer.language = cache.languages.get(record.language)
                importer.save()
                Importer.update_columns([importer])
                importers.append(importer)

            if 'column_field' in setup.fields:
                found = False
                for column in importer.columns:
                    if column.field.name == record.column_field:
                        found = True
                        break
                if found:
                    columns_to_save.append((column, record))
                    if 'column_name' in setup.fields:
                        column.name = record.column_name
                    if 'column_value' in setup.fields:
                        column.value = record.column_value
                    if 'column_format' in setup.fields:
                        column.format = record.column_format

        setup.current_record = None
        cls.importer_save(columns_to_save)
        return importers


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'meta': {
                    'string': 'Importer',
                    'model': 'importer.meta',
                    'chunked': False, # Deprecated
                    },
                })
        return methods
