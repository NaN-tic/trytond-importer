import base64
import logging
from unidecode import unidecode
import textdistance
import psycopg2
from trytond.pool import Pool
from trytond.model import fields, ModelView
from trytond.transaction import Transaction
from trytond.exceptions import UserError


logger = logging.getLogger(__name__)

class UserKeyError(UserError):
    pass


def nearest_text(text, texts):
    if len(text) == 1:
        return
    minimal = 10000
    best = None
    text = unidecode(text)
    text = text.lower()
    for t in texts:
        if text in t:
            minimal = 0
            best = t
            continue
        t = unidecode(t)
        t = t.lower()
        d = textdistance.levenshtein(text, t)
        if d < minimal:
            minimal = d
            best = t
    return best


# The reason we inherit from dict is that a Setup instance will be stored in
# the context which Tryton will try to serialize (convert to json) if it needs to
# execute a function in the worker. Trying to serialize Setup will crash unless
# it is from a type JSONEncoder understands by default

class Setup(dict):
    def __init__(self, on_error='skip', **kwargs):
        super().__init__(**kwargs)
        assert on_error in ('skip', 'log', 'raise'), on_error
        self.method = None
        self.on_error = on_error
        self.limit = 1000
        self.errors = []
        self.fields = []
        self.current_record = None
        self._saved = {}
        self.filename = None

    def error(self, message, record=None, **kwargs):
        if self.on_error == 'raise':
            raise UserError(message.format(**kwargs))
        if self.on_error == 'log':
            logger.warning(message.format(**kwargs))
        if record is None:
            record = self.current_record
        if len(self.errors) < self.limit:
            self.errors.append((record, message, kwargs))

    @staticmethod
    def get():
        return Transaction().context.get('importer_setup')

    def saved(self, model, pairs):
        self._saved.setdefault(model, []).extend(
            [(x[0].id, x[1]) for x in pairs])

    def deletes(self):
        pool = Pool()

        res = []
        for model, to_save in self._saved.items():
            Model = pool.get(model)
            ids = ', '.join(str(x[0]) for x in to_save)
            res.append(f'DELETE FROM {Model._table} WHERE id IN ({ids});')
        return '\n'.join(res)


class ImporterModel(ModelView):
    row_number = fields.Integer('Row Number', readonly=True)
    metadata = fields.Text('Metadata')

    def to_str(record, fields=None):
        res = []
        if fields is None:
            fields = sorted(record._fields.keys())
            fields.remove('id')
            fields.remove('row_number')
            fields.remove('metadata')
        for field in fields:
            if hasattr(record, field):
                res.append(f'{field}: {getattr(record, field)}')
        return ', '.join(res)

    @classmethod
    def importer_start(cls):
        pass

    def importer_context(self):
        return {}

    def importer_header(self, importing=True):
        pass

    @classmethod
    def importer_import(cls, records):
        raise NotImplementedError

    def importer_assign(self, record):
        cls = record.__class__
        for field in Setup.get().fields:
            if field in cls._fields:
                f = cls._fields[field]
                if isinstance(f, (fields.Many2One, fields.Many2Many,
                        fields.One2Many, fields.One2One)):
                    continue
                value = getattr(self, field, None)
                if value and isinstance(f, fields.Binary):
                    value = base64.b64decode(value)
                setattr(record, field, value)

    def importer_error(self, message, **kwargs):
        Setup.get().error(message, self, **kwargs)

    @classmethod
    def importer_save(cls, records):
        if not records:
            return

        cursor = Transaction().connection.cursor()
        setup = Setup.get()
        Model = records[0][0].__class__
        blocks = [records]
        while blocks:
            records = blocks.pop(0)
            to_save = [x[0] for x in records]
            # In some cases _values may be None (I think it is when the record
            # already existed and has not been modified)
            save_values = [x._values and x._values._copy() or None for x in
                to_save]
            cursor.execute('SAVEPOINT importer_save')
            try:
                logger.info('Saving %d records of %s', len(records), Model.__name__)
                Model.save(to_save)
                setup.saved(Model.__name__, records)
                cursor.execute('RELEASE SAVEPOINT importer_save')
                logger.info('Saved.')
            except (UserError, psycopg2.errors.InvalidTextRepresentation) as e:
                cursor.execute('ROLLBACK TO SAVEPOINT importer_save')
                if len(records) == 1:
                    setup.error(Model.__name__ + ': ' + getattr(e, 'message',
                            str(e)), records[0][1])
                    continue
                for record, sv in zip(to_save, save_values):
                    if not record._values:
                        record._values = sv

                logger.warning('Error saving a block of %d of %s records (%s). '
                    'Will split and retry.', len(records), Model.__name__, e)
                # TODO: Use itertools.batched from Python 3.12
                # for records in itertools.batched(records, len(records) // 10):
                #     blocks.insert(0, records)
                acc = []
                limit = len(records) // 10
                count = 0
                for record in records:
                    acc.append(record)
                    count += 1
                    if count >= limit:
                        blocks.insert(0, acc)
                        acc = []
                        count = 0
                if acc:
                    blocks.insert(0, acc)


class Cache:
    def __init__(self, model, key, domain=None, context=None,
             duplicates='first', case_sensitive=False,
             unaccent=False, required=True, cache_size=None):
        '''
        `model` is the name of the model to cache or the model class

        `key` maybe a field name or a function that returns a key. It can also be a list of keys. In this case the record will be added for each key value.

        `duplicates` can be one of:
        - `first` (default): will use the one of the records with the same key
        - `abort-on-load`: will raise an exception if there are duplicates on loading
        - `abort-on-use`: will raise an exception if there are duplicates and the key is used
        - `all`: will return all the records with the same key

        'required' indicates if the key is expected to exist
        '''
        if isinstance(model, str):
            self.model = model
        else:
            self.model = model.__name__
        if isinstance(key, (list, tuple)):
            keys = key
        else:
            keys = [key]

        def mygetter(key, record):
            value = self.treat(getattr(record, key))
            return value

        self._keys = []
        for key in keys:
            if isinstance(key, str):
                import functools
                key = functools.partial(mygetter, key)
            self._keys.append(key)
        self.domain = domain
        self.context = context
        self.case_sensitive = case_sensitive
        self.unaccent = unaccent
        self.required = required
        assert duplicates in ('first', 'abort-on-load', 'abort-on-use', 'all'), duplicates
        self.duplicates = duplicates
        self.cache_size = cache_size
        self._values = None

    def load(self):
        pool = Pool()
        Model = pool.get(self.model)
        self._values = {}

        context = self.context and self.context.copy() or {}
        if self.cache_size:
            context['_record_cache_size'] = self.cache_size
        with Transaction().set_context(context):
            for record in Model.search(self.domain or []):
                self.add(record)

    def treat(self, value):
        if isinstance(value, str):
            if not self.case_sensitive:
                value = value.lower()
            if self.unaccent:
                value = unidecode(value)
        elif isinstance(value, (tuple, list)):
            nvalue = []
            for v in value:
                v = self.treat(v)
                nvalue.append(v)
            value = tuple(nvalue)
        return value

    def get(self, key):
        self.ensure_loaded()
        key = self.treat(key)
        try:
            values = self._values[key]
        except KeyError:
            # If key is None we don't usually want the error to be reported
            if key and self.required:
                Setup.get().error(f'Key "{key}" not found accessing "{self.model}"')
            return
        if len(values) > 1 and self.duplicates == 'abort-on-use':
            Setup.get().error(f'Duplicate key "{key}" found accessing "{self.model}"')
        if self.duplicates == 'all':
            return values
        return values[0]

    def __getitem__(self, key):
        self.ensure_loaded()
        key = self.treat(key)
        try:
            values = self._values[key]
        except KeyError:
            Setup.get().error(f'Key "{key}" not found accessing "{self.model}"')
            return
        if len(values) > 1 and self.duplicates == 'abort-on-use':
            Setup.get().error(f'Duplicate key "{key}" found accessing "{self.model}"')
        if self.duplicates == 'all':
            return values
        return values[0]

    def __setitem__(self, key, value):
        self.ensure_loaded()
        key = self.treat(key)
        self._values[key] = [value]

    def __contains__(self, key):
        self.ensure_loaded()
        key = self.treat(key)
        return key in self._values

    def add(self, record):
        self.ensure_loaded()
        for key in self._keys:
            kv = key(record)
            if kv in self._values:
                if self.duplicates == 'abort-on-load':
                    Setup.get().error(f'Duplicate key "{kv}" found loading model '
                        '"{model}"')
                    continue
                elif self.duplicates == 'first':
                    continue
            self._values.setdefault(kv, []).append(record)

    def keys(self):
        self.ensure_loaded()
        return self._values.keys()

    def values(self):
        self.ensure_loaded()
        if self.duplicates == 'all':
            return self._values.values()
        return [x[0] for x in self._values.values()]

    def ensure_loaded(self):
        if self._values is None:
            self.load()
