import re
import csv
import json
import yaml
import pytz
import urllib.request
import decimal
import tempfile
from decimal import Decimal
import openpyxl
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.writer.excel import save_workbook
import textdistance
import datetime
import charset_normalizer
from io import StringIO, BytesIO
from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder, Eval, Bool
from trytond.transaction import Transaction
from trytond.exceptions import UserError, UserWarning
from trytond.i18n import gettext
from trytond.config import config
from trytond.rpc import RPC
from trytond.report import Report
from trytond.modules.currency.fields import Monetary


DISTANCE_THRESHOLD = config.getfloat('importer', 'distance_threshold',
    default=0.0)

data_sources = [
    ('binary', 'File'),
    ('text', 'Copy & Paste'),
    ('url', 'URL'),
    ('sql', 'SQL'),
    ]

def save_virtual_workbook(workbook):
    with tempfile.NamedTemporaryFile() as tmp:
        save_workbook(workbook, tmp.name)
        with open(tmp.name, 'rb') as f:
            return f.read()

def grouped_slice(records, count=None):
    'grouped_slice implementation that works with iterators'
    if count is None:
        count = Transaction().database.IN_MAX

    chunk = []
    counter = 0
    for record in records:
        chunk.append(record)
        counter += 1
        if counter % count == 0:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


class Data:
    def __init__(self, data_source, binary_data, text_data, url_data,
            conn=None, sql=None):
        self.data_source = data_source
        self.binary_data = binary_data
        self.text_data = text_data
        self.url_data = url_data
        self.connection = conn
        self.sql = sql

    @staticmethod
    def to_str(d):
        return charset_normalizer.from_bytes(d).best().output().decode('utf-8')

    def get_data_file(self, force_text=False):
        'force_text makes the method always return a StringIO.'
        'Required by csv reader, which only supports text files.'

        if self.data_source == 'binary' and self.binary_data:
            if force_text:
                return StringIO(self.to_str(self.binary_data))
            return BytesIO(self.binary_data)
        elif self.data_source == 'text' and self.text_data:
            return StringIO(self.text_data)
        elif self.data_source == 'url' and self.url_data:
            url = self.url_data
            if ('docs.google.com' in url and 'export' not in url):
                # Expected URL:
                # https://docs.google.com/spreadsheets/d/19DjZIGvNj1-Z4e4Q4SGqlrnKSAQyMz0JDhhgs2Xbf8w/edit#gid=0
                # New URL:
                # https://docs.google.com/spreadsheets/d/19DjZIGvNj1-Z4e4Q4SGqlrnKSAQyMz0JDhhgs2Xbf8w/export?format=xlsx&id=19DjZIGvNj1-Z4e4Q4SGqlrnKSAQyMz0JDhhgs2Xbf8w&gid=0
                main, _, extra = url.rpartition('/')
                url = main + '/export?format=xlsx&gid=0'
                if '#' in extra:
                    url += '&' + extra.split('#')[-1]
                try:
                    with urllib.request.urlopen(url) as f:
                        data = f.read()
                except:
                    # In some cases we've found that adding gid and other
                    # parameters does not work. In those cases, we try again
                    # without them.
                    url = main + '/export?format=xlsx'
                    with urllib.request.urlopen(url) as f:
                        data = f.read()
            else:
                with urllib.request.urlopen(url) as f:
                    data = f.read()
            if force_text:
                return StringIO(self.to_str(data))
            return BytesIO(data)

        # If no data source or data specified return empty content
        if force_text:
            return StringIO(str())
        return BytesIO(bytes())

    def get_data(self):
        'Return a list of lists'
        # Process XLSX files
        try:
            book = openpyxl.load_workbook(filename=self.get_data_file(),
                data_only=True)
        except:
            book = None
        if book:
            sheet = book.active
            rows = []
            for row in sheet.iter_rows():
                # Limit the number of columns to a maximum of 1024.
                # We've found with some spreadsheets with many columns (most of
                # them empty) that not limiting the number of columns causes
                # openpyxl to load data incorrectly. Using 1600 instead of 1024
                # fails too, so we set the limit to 1024 which is the maximum
                # number of columns allowed by LibreOffice
                rows.append([x.value for x in row[:1024]])
            return {
                'type': 'xlsx',
                'has_header': False,
                'header_reliable': False,
                'rows': rows,
                }

        # Process JSON and YAML files
        try:
            content = json.load(self.get_data_file())
            type = 'json'
        except:
            try:
                content = yaml.safe_load(self.get_data_file())
                type = 'yaml'
            except:
                content = None
        if isinstance(content, list):
            if all(isinstance(x, list) for x in content):
                return {
                    'type': type,
                    'has_header': False,
                    'header_reliable': True,
                    'rows': content,
                    }
            if all(isinstance(x, dict) for x in content):
                # TODO: We're considering that all records have all the keys
                rows = []
                rows.append([x for x in sorted(content[0].keys())])
                for item in content:
                    row = []
                    for key in sorted(item.keys()):
                        row.append(item[key])
                    rows.append(row)
                return {
                    'type': type,
                    'has_header': True,
                    'header_reliable': True,
                    'rows': rows,
                    }

        # Process CSV files
        try:
            data = self.get_data_file(force_text=True)
            rows = []
            sniffer = csv.Sniffer()
            chunk = data.read(1024)
            dialect = sniffer.sniff(chunk)
            has_header = sniffer.has_header(chunk)
            data.seek(0)
            reader = csv.reader(data, dialect)
            for row in reader:
                rows.append(row)
            return {
                'type': 'csv',
                'has_header': has_header,
                'header_reliable': False,
                'rows': rows,
                }
        except:
            pass

        if self.connection:
            try:
                cursor = self.connection.cursor()
                cursor.execute(self.sql)
                rows = [[item[0] for item in cursor.description]]
                rows += cursor.fetchall()
                return {
                    'type': 'sql',
                    'has_header': True,
                    'header_reliable': True,
                    'rows': rows,
                    }
            except Exception:
                pass
        return {
            'type': 'none',
            'has_header': False,
            'header_reliable': False,
            'rows': [],
            }


class Importer(ModelSQL, ModelView):
    'Importer'
    __name__ = 'importer'
    name = fields.Char('Name', required=True)
    method = fields.Selection('get_methods', 'Format', required=True)
    model = fields.Function(fields.Many2One('ir.model', 'Model'),
        'on_change_with_model')
    template = fields.Boolean('Template', help="Check to indicate that this "
        "importer is a template and thus should appear in the import wizard.")
    has_header = fields.Boolean('Has Header?')
    use_header = fields.Boolean('Use Header?', states={
            'invisible': ~Eval('has_header'),
            }, depends=['has_header'])
    data_source = fields.Selection(
        [(None, ''), ] + data_sources, 'Data Source')
    sql_source = fields.Selection([(None, ''), ], 'SQL Source', states={
        'invisible': ~Eval('data_source').in_(['sql']),
        'required': Eval('data_source').in_(['sql']),
        }, depends=['data_source'])
    server = fields.Char('Server', states={
        'invisible': ~Eval('data_source').in_(['sql']),
        'required': Eval('data_source').in_(['sql']),
        }, depends=['data_source'])
    user = fields.Char('User', states={
        'invisible': ~Eval('data_source').in_(['sql']),
        'required': Eval('data_source').in_(['sql']),
        })
    password = fields.Char('Password', states={
        'invisible': ~Eval('data_source').in_(['sql']),
        'required': Eval('data_source').in_(['sql']),
        })
    database = fields.Char('Database', states={
        'invisible': ~Eval('data_source').in_(['sql']),
        'required': Eval('data_source').in_(['sql']),
        })
    schema = fields.Char('Schema', states={
        'invisible': ~Eval('data_source').in_(['sql']),
        })
    where = fields.Char('Where', states={
        'invisible': ~Eval('data_source').in_(['sql']),
        })
    binary_data = fields.Binary('Data', states={
            'invisible': Eval('data_source') != 'binary',
            }, filename='binary_file_name')
    binary_file_name = fields.Text('Binary File Name')
    sql_data = fields.Selection([(None, '')], "SQL Queries", states={
        'invisible': ~Eval('data_source').in_(['sql']),
        'required': Eval('data_source').in_(['sql']),
        })
    text_data = fields.Text('Data', states={
            'invisible': Eval('data_source') != 'text',
            })
    url_data = fields.Char('Data URL', states={
            'invisible': Eval('data_source') != 'url',
            })
    columns = fields.One2Many('importer.column', 'importer', 'Column')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'sync_columns': {},
                'detect': {
                    'icon': 'importer-detect',
                    'invisible': ~Bool(Eval('data_source')),
                    },
                'import_': {
                    'icon': 'importer-upload',
                    'invisible': ~Bool(Eval('data_source')),
                    },
                'check_connection': {
                    'icon': 'importer-upload',
                    'invisible': ~Bool(Eval('data_source').in_(['sql'])),
                    },
                })

    @classmethod
    def create(cls, vlist):
        importers = super().create(vlist)
        cls.sync_columns(importers)
        return importers

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        actions = iter(args)
        for importers, values in zip(actions, actions):
            for importer in importers:
                if 'method' in values and values['method'] != importer.method:
                    key = 'importer_change_method'
                    if Warning.check(key):
                        raise UserWarning(key,
                            gettext('importer.change_method_warning',
                                name=importer.name))
        super().write(*args)
        cls.sync_columns(sum(args[::2], []))

    @classmethod
    @ModelView.button
    def check_connection(cls, importers):
        for importer in importers:
            if importer.data_source != 'sql':
                continue
            method = getattr(importer, "check_connection_%s" %
                importer.sql_source)
            method()

    def get_connection(self, fail=True):
        if self.data_source != 'sql':
            return
        method = getattr(self, "get_connection_%s" % self.sql_source)
        return method(fail=fail)

    def get_sql(self):
        if self.data_source != 'sql':
            return
        with open(self.get_url_file()) as sql_file:
            sql = sql_file.read()
            sql = sql.format(schema=self.schema, domain=self.where)
            return sql

    @classmethod
    @ModelView.button
    def sync_columns(cls, importers):
        pool = Pool()
        Column = pool.get('importer.column')

        to_delete = []
        to_save = []
        for importer in importers:
            if not importer.model:
                continue
            needed = set()
            for field in importer.model.fields:
                needed.add(field)

            for column in importer.columns:
                if column.field in needed:
                    needed.remove(column.field)
                else:
                    to_delete.append(column)

            for field in needed:
                if field.name == 'id':
                    continue
                column = Column()
                column.importer = importer
                column.field = field
                to_save.append(column)
        Column.delete(to_delete)
        Column.save(to_save)

    @classmethod
    @ModelView.button
    def detect(cls, importers, distance_threshold=None):
        pool = Pool()
        Column = pool.get('importer.column')

        columns = []
        for importer in importers:
            conn = importer.get_connection()
            sql = importer.get_sql()
            data = Data(importer.data_source, importer.binary_data,
                importer.text_data, importer.url_data, conn, sql)
            item = data.get_data()
            rows = item['rows']
            has_header = item['has_header']
            header_reliable = item['header_reliable']
            use_header = has_header
            if rows and (has_header or not header_reliable):
                use_header = importer.detect_header(rows[0], distance_threshold)
                columns += importer.columns

            importer.has_header = use_header
            importer.use_header = use_header

        cls.save(importers)
        Column.save(columns)

    def detect_header(self, row, distance_threshold):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Field = pool.get('ir.model.field')

        if distance_threshold is None:
            distance_threshold = DISTANCE_THRESHOLD

        field_ids = []
        strings = {}
        for column in self.columns:
            field_ids.append(column.field.id)
            strings[column.field] = [column.field.name,
                column.field.field_description]

        langs = Lang.search([
                ('translatable', '=', True),
                ('id', '!=', Transaction().context.get('lang', -1)),
                ])
        for lang in langs:
            with Transaction().set_context(language=lang.code):
                for field in Field.browse(field_ids):
                    strings[field].append(field.field_description)

        use_header = False
        lev = textdistance.Levenshtein()
        for column in self.columns:
            row_minimum = (9, None)
            for header in row:
                header = str(header)
                header_minimum = 9
                for string in strings[column.field]:
                    value = lev.normalized_distance(header.lower(),
                        string.lower())
                    header_minimum = min(header_minimum, value)
                if header_minimum < row_minimum[0]:
                    row_minimum = (header_minimum, header)
            if row_minimum[0] <= distance_threshold:
                column.name = row_minimum[1]
                use_header = True
            else:
                column.name = None
        return use_header

    @classmethod
    def get_methods(cls):
        return [(k, v['string']) for k, v in cls._get_methods().items()]

    @classmethod
    def _get_methods(cls):
        return {}

    @property
    def chunked(self):
        info = self._get_methods()
        return info[self.method]['chunked']

    @property
    def requires_records(self):
        # Some importers (such as country) don't really require records as
        # input
        info = self._get_methods()
        return info[self.method].get('requires_records', True)

    @fields.depends('method')
    def on_change_with_model(self, name=None):
        pool = Pool()
        Model = pool.get('ir.model')
        item = self._get_methods().get(self.method)
        if not item:
            return
        models = Model.search([('model', '=', item['model'])], limit=1)
        if models:
            return models[0].id

    @classmethod
    @ModelView.button_action('importer.act_import_wizard')
    def import_(cls, importers):
        pass

    def data_to_records(self, data=None):
        # Records will be an iterator
        method = getattr(self, 'import_' + self.method)
        new_records = []
        if self.requires_records:
            if self.chunked:
                for records in grouped_slice(self.get_records(data=data)):
                    new_records += method(records)
            else:
                new_records += method(self.get_records(data=data))
        else:
            new_records = method()
        return new_records

    def get_records(self, raise_errors=True, data=None):
        '''
        data is a dictionary with the structure returned by get_data()
        '''
        pool = Pool()
        methods = self._get_methods()
        Model = pool.get(methods[self.method]['model'])

        if data is None:
            conn = self.get_connection()
            sql = self.get_sql()
            data = Data(self.data_source, self.binary_data, self.text_data,
                self.url_data, conn, sql)
            data = data.get_data()

        rows = data['rows']
        if not rows:
            return []
        indexes = self.get_field_indexes(rows)
        if self.has_header:
            rows = rows[1:]

        # We want to make sure we set all fields, even if the Importer record
        # has not been updated since the last change of the model
        missing_fields = ({f.name for f in self.model.fields}
            - {c.field.name for c in self.columns})

        for row in rows:
            if not any(row):
                continue
            record = Model()
            # Loop on columns so we ensure we set a value for all fields
            # hence importer methods can rely on the field to exist even if it
            # is None
            for column in self.columns:
                index = indexes.get(column.field.name)
                if index is None:
                    value = None
                else:
                    try:
                        value = column.cast_value(row[index])
                    except IndexError:
                        if raise_errors:
                            raise UserError(gettext('importer.invalid_index',
                                    column=column.rec_name,
                                    importer=self.rec_name))
                        else:
                            value = None
                try:
                    setattr(record, column.field.name, value)
                except TypeError:
                    pass

            for field in missing_fields:
                setattr(record, field, None)

            yield record

    def get_field_indexes(self, rows):
        indexes = {}
        if self.use_header:
            header = rows[0]
            hi = {}
            for pos in range(len(header)):
                hi[header[pos]] = pos

            for column in self.columns:
                index = hi.get(column.name)
                if index is None:
                    continue
                indexes[column.field.name] = index
        else:
            indexes = {}
            for column in self.columns:
                if not column.name:
                    continue
                try:
                    index = int(column.name) - 1
                except ValueError:
                    # Convert column name to index
                    index = 0
                    for letter in column.name.upper():
                        index *= 26
                        index += ord(letter) - ord('A') + 1
                    index -= 1
                indexes[column.field.name] = index
        return indexes

    @classmethod
    def datetime_to_utc(cls, datetime_, timezone=None):
        pool = Pool()
        Company = pool.get('company.company')
        company = Company(Transaction().context.get('company'))

        if company.timezone and isinstance(datetime_, datetime.date):
            timezone = pytz.timezone(company.timezone)
            company_datetime = timezone.localize(datetime_, is_dst=None)
            datetime_ = company_datetime.astimezone(pytz.utc)
        return datetime_


class ImporterColumn(ModelSQL, ModelView):
    'Importer Column'
    __name__ = 'importer.column'

    importer = fields.Many2One('importer', 'Importation', required=True,
        ondelete='CASCADE')
    model = fields.Function(fields.Many2One('ir.model', 'Model'),
        'on_change_with_model')
    field = fields.Many2One('ir.model.field', 'Field', ondelete='CASCADE',
        required=True, readonly=True,
        domain=[('model', '=', Eval('model'))], depends=['model'])
    name = fields.Char('Column Name')
    format = fields.Selection('_get_formats', 'Format')
    examples = fields.Function(fields.Char('Examples'),
        'get_examples')

    @fields.depends('importer', '_parent_importer.model')
    def on_change_with_model(self, name=None):
        if self.importer and self.importer.model:
            return self.importer.model.id

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('field.field_description', 'ASC'))
        cls.__rpc__.update(
            autocomplete_name=RPC(instantiate=0),
            )

    @classmethod
    def _get_formats(cls):
        return [
            (None, ''),
            ('keep-spaces', 'Keep Spaces'),
            ('date-%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S'),
            ('date-%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S'),
            ('date-%d/%m/%Y', '%d/%m/%Y'),
            ('date-%Y-%m-%d', '%Y-%m-%d'),
            ('decimal-,', 'Decimal (,)'),
            ('decimal-.', 'Decimal (.)'),
            ("decimal-'", "Decimal (')"),
            ]

    @fields.depends('importer', '_parent_importer.has_header',
        '_parent_importer.use_header', '_parent_importer.id',
        '_parent_importer.data_source', '_parent_importer.binary_data',
        '_parent_importer.text_data', '_parent_importer.url_data')
    def autocomplete_name(self):
        pool = Pool()
        Importer = pool.get('importer')

        if not self.importer:
            return
        if not self.importer.has_header or not self.importer.use_header:
            return
        if (self.importer.id >= 0 and isinstance(
                    self.importer.binary_data, int)):
            # The client will send the size of the binary field instead of its
            # content if it does not have it loaded.
            importer = Importer(self.importer.id)
            binary_data = importer.binary_data
        else:
            binary_data = self.importer.binary_data
        conn = self.importer.get_connection(fail=False)
        if not conn:
            return []
        sql = self.importer.get_sql()
        data = Data(self.importer.data_source, binary_data,
            self.importer.text_data, self.importer.url_data, conn, sql)
        rows = data.get_data()['rows']
        if rows:
            return sorted([x for x in rows[0] if x])
        return []

    @classmethod
    def get_examples(self, columns, name):
        pool = Pool()
        Lang = pool.get('ir.lang')

        language = Transaction().context.get('language') or 'en'
        language, = Lang.search([('code', '=', language)])

        def value_to_str(value):
            if isinstance(value, str):
                return value
            if isinstance(value, datetime.date):
                return language.strftime(value)
            return str(value)

        importers = {}
        for column in columns:
            if column.importer in importers:
                continue
            records = []
            for record in column.importer.get_records(raise_errors=False):
                records.append(record)
                if len(records) >= 3:
                    break
            importers[column.importer] = records

        res = {}
        for column in columns:
            records = importers[column.importer]
            values = [getattr(x, column.field.name) for x in records]
            if all([x is None for x in values]):
                res[column.id] = None
            else:
                res[column.id] = ' | '.join([value_to_str(x) for x in values])
        return res


    def get_selection_dict(self, model, field):
        Lang = Pool().get('ir.lang')
        Model = Pool().get(model)

        d = {}

        for language in Lang.search([('translatable', '=', True)]):
            with Transaction().set_context(language=language.code):
                for selection in Model.fields_get([field])[field]["selection"]:
                    if selection[0] not in d:
                        d[selection[0]] = selection[0]
                    if selection[1] not in d:
                        d[selection[1]] = selection[0]
        return d


    def cast_value(self, value):
        if value is None:
            return value
        ttype = self.field.ttype
        help = self.field.help

        if ttype in ('char', 'text'):
            if help.startswith('selection|'):
                _, model, field = help.split('|')
                d = self.get_selection_dict(model, field)
                if value.strip() not in d:
                    raise UserError(gettext(
                        'importer.value_not_in_selection', field=field))
                return d[value.strip()]
            if isinstance(value, str):
                if self.format and self.format == 'keep-spaces':
                    return value
                return value.strip()
            else:
                return str(value)
        elif ttype in ('integer', 'float', 'numeric'):
            if isinstance(value, str):
                if self.format and self.format.startswith('decimal-'):
                    decimal_symbol = self.format[len('decimal-'):]
                    for symbol in " ,.'":
                        if symbol == decimal_symbol:
                            continue
                        value = value.replace(symbol, '')
                    value = value.replace(decimal_symbol, '.')
            try:
                pool = Pool()
                ModelClass = pool.get(self.field.model.model)
                field = getattr(ModelClass, self.field.name)
                if ttype == 'float':
                    value = float(value)
                    if field.digits:
                        value = round(value, field.digits[1])
                    return value
                elif ttype == 'integer':
                    return int(value)
                elif ttype == 'numeric':
                    if isinstance(value, float):
                        value = Decimal('%.10f' % value)
                    else:
                        value = Decimal(value)
                    if field.digits:
                        value = value.quantize(Decimal(str(
                                    10 ** -field.digits[1])))
                    return value
            except (ValueError, decimal.InvalidOperation):
                # TODO: Raise Error
                return None
        elif ttype == 'date':
            if isinstance(value, str):
                value = value.strip()
                if self.format and self.format.startswith('date-'):
                    format = self.format[len('date-'):]
                else:
                    format = '%Y-%m-%d'
                try:
                    return datetime.datetime.strptime(value, format).date()
                except ValueError:
                    # TODO: Raise Error
                    return None
            elif not isinstance(value, datetime.date):
                return None
        elif ttype in ('datetime', 'timestamp'):
            if isinstance(value, str):
                value = value.strip()
                if self.format and self.format.startswith('date-'):
                    format = self.format[len('date-'):]
                else:
                    format = '%Y-%m-%d'
                try:
                    return datetime.datetime.strptime(value, format)
                except ValueError:
                    # TODO: Raise Error
                    return None
            elif not isinstance(value, (datetime.datetime, datetime.date)):
                return None
        elif ttype == 'boolean':
            value = str(value).strip()
            if value.lower() in ('false', 'off', '0', ''):
                return False
            else:
                return True
        return value

    @classmethod
    def validate(cls, columns):
        for column in columns:
            column.check_name()

    def check_name(self):
        if not self.name or self.importer.use_header:
            return
        try:
            int(self.name)
        except ValueError:
            if not re.fullmatch('[A-Z]+', self.name):
                raise UserError(gettext('importer.invalid_column_name',
                        name=self.name, column=self.rec_name,
                        importer=self.importer))


class ImportAsk(ModelView):
    'Import Ask'
    __name__ = 'importer.import.ask'
    importer = fields.Many2One('importer', 'Importer', required=True, domain=[
            ('template', '=', True),
            ])
    data_source = fields.Selection(data_sources, 'Data Source', required=True)
    binary_data = fields.Binary('Data', states={
            'invisible': Eval('data_source') != 'binary',
            })
    text_data = fields.Text('Data', states={
            'invisible': Eval('data_source') != 'text',
            })
    url_data = fields.Char('Data URL', states={
            'invisible': Eval('data_source') != 'url',
            })


class AskAndImport(Wizard):
    'Import'
    __name__ = 'importer.ask_and_import'
    start_state = 'ask'
    ask = StateView('importer.import.ask', 'importer.import_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Import', 'import_', 'importer-upload', default=True),
            ])
    import_ = StateAction('importer.act_import_open')

    def do_import_(self, action):
        conn = self.ask.importer.get_connection()
        sql = self.ask.importer.get_sql()
        data = Data(self.ask.data_source, self.ask.binary_data,
            self.ask.text_data, self.ask.url_data, conn, sql)
        records = self.ask.importer.data_to_records(data.get_data())
        if not records:
            raise UserError(gettext('importer.no_records_imported',
                importer=self.ask.importer.rec_name))

        # TODO: One tab for each model
        models = {}
        for record in records:
            models.setdefault(record.__name__, []).append(record)

        for model, records in models.items():
            action['res_model'] = model
            action['pyson_domain'] = PYSONEncoder().encode(
                [('id', 'in', [x.id for x in records])],
                )
        return action, {}

    def transition_import_(self):
        return 'end'


class Import(Wizard):
    'Import'
    __name__ = 'importer.import'
    start_state = 'import_'
    import_ = StateAction('importer.act_import_open')

    def do_import_(self, action):
        # TODO: Support importing several importers at once
        records = self.record.data_to_records()
        if not records:
            raise UserError(gettext('importer.no_records_imported',
                importer=self.record.rec_name))

        models = {}
        for record in records:
            models.setdefault(record.__name__, []).append(record)

        for model, records in models.items():
            action['res_model'] = model
            action['pyson_domain'] = PYSONEncoder().encode(
                [('id', 'in', [x.id for x in records])],
                )
        return action, {}

    def transition_import_(self):
        return 'end'


class ExcelTemplate(Report):
    'Excel Template'
    __name__ = 'importer.excel.template'

    @classmethod
    def execute(cls, ids, data):
        if not ids:
            return
        cls.check_access()
        pool = Pool()
        Importer = pool.get('importer')
        importer = Importer(ids[0])
        wb = Workbook()
        ws = wb.active
        header = []
        for column in importer.columns:
            header.append(column.field.field_description)
        header = tuple(header)
        ws.append(header)

        for column in importer.columns:
            if column.field.help and column.field.help.startswith("selection"):
                _, model, field_name = column.field.help.split("|")
                ModelClass = pool.get(model)
                selections = ModelClass.fields_get([field_name])[field_name]['selection']
                selections = [i[0] for i in selections]
                c = 2
                for selection in selections:
                    ws.cell(row=c, column=importer.columns.index(column)+1).value = selection
                    c+= 1

        for column, number in zip(importer.columns, range(1, len(header) + 1)):
            c = column.field.help
            if c:
                ws.cell(row=1, column=number).comment = Comment(c, "Tryton")
        return ('xlsx', save_virtual_workbook(wb), False, importer.name)
