import logging
from types import SimpleNamespace
from trytond.pool import Pool
from trytond.model import fields, ModelView
from trytond.model.modelsql import RequiredValidationError
from trytond.transaction import Transaction
from trytond.exceptions import UserError


logger = logging.getLogger(__name__)

class UserKeyError(UserError):
    pass


def record_to_str(record, fields=None):
    res = []
    if fields is None:
        fields = sorted(record._fields.keys())
    for field in fields:
        if hasattr(record, field):
            res.append(f'{field}: {getattr(record, field)}')
    return ', '.join(res)


class Setup(SimpleNamespace):
    def __init__(self, on_error='skip', **kwargs):
        super().__init__(**kwargs)
        assert on_error in ('skip', 'log', 'raise'), on_error
        self.method = None
        self.on_error = on_error
        self.limit = 5000
        self.errors = []
        self.fields = []

    def error(self, message, record=None, **kwargs):
        if self.on_error == 'raise':
            raise UserError(message.format(**kwargs))
        if self.on_error == 'log':
            logger.warning(message.format(**kwargs))
        if len(self.errors) < self.limit:
            self.errors.append((record, message, kwargs))

    @staticmethod
    def get():
        return Transaction().context.get('importer_setup')


class ImporterModel(ModelView):
    row_number = fields.Integer('Row Number', readonly=True)

    @classmethod
    def importer_start(cls):
        pass

    def importer_context(self):
        return {}

    def importer_header(self):
        pass

    @classmethod
    def importer_import(cls, records):
        pass

    def importer_assign(self, record):
        cls = record.__class__
        for field in Setup.get().fields:
            if field in cls._fields:
                f = cls._fields[field]
                if isinstance(f, (fields.Many2One, fields.Many2Many,
                        fields.One2Many, fields.One2One)):
                    continue
                setattr(record, field, getattr(self, field, None))

    def importer_error(self, message, **kwargs):
        Setup.get().error(message, self, **kwargs)

    @classmethod
    def importer_save(cls, records):
        if not records:
            return
        setup = Setup.get()
        Model = records[0].__class__
        blocks = [records]
        while blocks:
            records = blocks.pop(0)
            try:
                print('Saving %d records' % len(records))
                Model.save(records)
                print('Saved')
            except RequiredValidationError:
                raise
            except UserError as e:
                if len(records) == 1:
                    setup.error(e.message, records[0])
                    continue
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
             duplicates='first', case_sensitive=False, required=True):
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
            value = getattr(record, key)
            if isinstance(value, str) and not case_sensitive:
                value = value.lower()
            return value

        self.keys = []
        for key in keys:
            if isinstance(key, str):
                import functools
                key = functools.partial(mygetter, key)
            self.keys.append(key)
        self.domain = domain
        self.context = context
        self.case_sensitive = case_sensitive
        self.required = required
        assert duplicates in ('first', 'abort-on-load', 'abort-on-use', 'all'), duplicates
        self.duplicates = duplicates
        self.values = None

    def load(self):
        pool = Pool()
        Model = pool.get(self.model)
        self.values = {}
        with Transaction().set_context(self.context):
            for record in Model.search(self.domain or []):
                self.add(record)

    def get(self, key):
        if self.values is None:
            self.load()
        if isinstance(key, str) and not self.case_sensitive:
            key = key.lower()
        try:
            values = self.values[key]
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
        if self.values is None:
            self.load()
        if isinstance(key, str) and not self.case_sensitive:
            key = key.lower()
        try:
            values = self.values[key]
        except KeyError:
            Setup.get().error(f'Key "{key}" not found accessing "{self.model}"')
            return
        if len(values) > 1 and self.duplicates == 'abort-on-use':
            Setup.get().error(f'Duplicate key "{key}" found accessing "{self.model}"')
        if self.duplicates == 'all':
            return values
        return values[0]

    def __setitem__(self, key, value):
        if self.values is None:
            self.load()
        if isinstance(key, str) and not self.case_sensitive:
            key = key.lower()
        self.values[key] = [value]

    def __contains__(self, key):
        if self.values is None:
            self.load()
        if isinstance(key, str) and not self.case_sensitive:
            key = key.lower()
        return key in self.values

    def add(self, record):
        if self.values is None:
            self.load()
        for key in self.keys:
            kv = key(record)
            if kv in self.values:
                if self.duplicates == 'abort-on-load':
                    Setup.get().error(f'Duplicate key "{kv}" found loading model '
                        '"{model}"')
                    continue
                elif self.duplicates == 'first':
                    continue
            self.values.setdefault(kv, []).append(record)
