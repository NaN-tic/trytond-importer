from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta


class ImporterSequence(ModelView):
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


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'sequence': {
                    'string': 'Sequence',
                    'model': 'importer.sequence',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_sequence(cls, records):
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
        sequences = {x.name: x for x in Type.search([])}
        for record in records:
            if record.strict:
                Sequence = SequenceStrict
            else:
                Sequence = SequenceNotStrict

            if not record.sequence_type:
                raise UserError(gettext('importer.msg_sequence_type_required'))
            if record.sequence_type not in sequences:
                raise UserError(gettext('importer.msg_sequence_type_not_found',
                        type=record.sequence_type))
            sequence_type = sequences.get(record.sequence_type)

            sequences = Sequence.search([('name', 'in', records)], limit=1)
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

        return sequences

