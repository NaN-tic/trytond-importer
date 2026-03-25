from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from .tools import ImporterModel
from trytond.exceptions import UserError
from trytond.i18n import gettext


class ImporterSequence(ImporterModel):
    'Importer Party Configuration'
    __name__ = 'importer.sequence'

    name = fields.Char('Name')
    sequence_type = fields.Char('Sequence Type')
    company_name = fields.Char('Company Name')
    prefix = fields.Char("Sequence prefix")
    suffix = fields.Char("Sequence suffix")
    padding = fields.Integer("Sequence Padding")
    number_next = fields.Integer("Sequence Number Next")
    strict = fields.Boolean('Strict')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        try:
            Company = pool.get('company.company')
        except KeyError:
            Company = None
        SequenceNotStrict = pool.get('ir.sequence')
        SequenceStrict = pool.get('ir.sequence.strict')
        Type = pool.get('ir.sequence.type')

        if Company:
            companies = {x.party.name: x for x in Company.search([])}
        else:
            companies = {}
        types = {x.name: x for x in Type.search([])}
        to_return = []
        for record in records:
            if record.strict:
                Sequence = SequenceStrict
            else:
                Sequence = SequenceNotStrict

            if not record.sequence_type:
                raise UserError(gettext('importer.msg_sequence_type_required'))
            if record.sequence_type not in types:
                raise UserError(gettext('importer.msg_sequence_type_not_found',
                        type=record.sequence_type))
            sequence_type = types.get(record.sequence_type)

            domain = [('name', '=', record.name)]
            if companies and record.company_name:
                domain.append(('company.party.name', '=', record.company_name))
            sequences = Sequence.search(domain, limit=1)
            if not sequences:
                sequence = Sequence()
                sequence.name = record.name
            else:
                sequence, = sequences

            if companies and record.company_name:
                if not record.company_name in companies:
                    raise UserError(
                        gettext('importer.msg_import_company_not_found',
                            company=record.company_name))
                sequence.company = companies.get(record.company_name)

            sequence.sequence_type = sequence_type
            sequence.prefix = record.prefix
            sequence.suffix = record.suffix
            sequence.padding = record.padding or 1
            sequence.number_next = record.number_next or 1
            sequence.save()
            to_return.append(sequence)

        return to_return


class ImporterLanguage(ImporterModel):
    'Importer Language'
    __name__ = 'importer.language'

    code = fields.Char('Code')
    name = fields.Char('Name')
    translatable = fields.Boolean('Translatable')
    parent = fields.Char('Parent')
    date = fields.Char('Date Format')
    decimal_point = fields.Char('Decimal Point')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Language = pool.get('ir.lang')

        to_save = []
        for record in records:
            languages = Language.search([('code', '=', record.code)])
            if languages:
                language, = languages
            else:
                language = Language()
            if record.name:
                language.name = record.name
            if not record.translatable is None:
                language.translatable = record.translatable
            if record.parent:
                language.parent = record.parent
            if record.date:
                language.date = record.date
            if record.decimal_point:
                language.decimal_point = record.decimal_point

            to_save.append(language)

        Language.load_translations(to_save)
        Language.save(to_save)
        return to_save


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'language': {
                    'string': 'Languages',
                    'model': 'importer.language',
                    },
                'sequence': {
                    'string': 'Sequence',
                    'model': 'importer.sequence',
                    },
                })
        return methods
