from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.transaction import Transaction
from trytond.tools import grouped_slice


class ImporterProductionBom(ModelView):
    'Importer Production Bom'
    __name__ = 'importer.production.bom'

    name = fields.Char('Name')
    input_product = fields.Char('Product Input')
    input_quantity = fields.Float('Product Input Quantity')
    input_uom = fields.Char('Product Input UoM')
    output_product = fields.Char('Product Output')
    output_quantity = fields.Float('Product Output Quantity')
    output_uom = fields.Char('Product Output UoM')


class ImporterProductionConfiguration(ModelView):
    'Importer Production Configuration'
    __name__ = 'importer.production.configuration'

    sequence_prefix = fields.Char("Sequence prefix")
    sequence_suffix = fields.Char("Sequence suffix")
    sequence_padding = fields.Integer("Sequence padding")
    sequence_number_next = fields.Integer("Sequence number next")


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'production_bom': {
                    'string': 'Production BOM',
                    'model': 'importer.production.bom',
                    'chunked': True,
                    },
                'production_configuration': {
                    'string': 'Production configuration',
                    'model': 'importer.production.configuration',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def _import_production_bom_input_hook(cls, record, input):
        pass

    @classmethod
    def _import_production_bom_output_hook(cls, record, output):
        pass

    @classmethod
    def import_production_bom(cls, records):
        """
        - Create new BOM and inputs and outputs
        - In case BOM exists, create new inputs or outputs; not update current inputs/outputs
        """
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        Bom = pool.get('production.bom')
        BomInput = pool.get('production.bom.input')
        BomOutput = pool.get('production.bom.output')

        uoms = {}
        for uom in Uom.search([]):
            uoms[uom.name.lower()] = uom
            uoms[uom.symbol.lower()] = uom

        products = dict((x.code, x) for x in Product.search([
                    ('code', '!=', None),
                    ('code', '!=', ''),
                    ]))
        boms = dict((x.name, x) for x in Bom.search([]))

        boms_found = []
        boms_to_save = []
        inputs_to_save = []
        outputs_to_save = []
        previous_header = None
        for record in records:
            header = record.name

            if boms.get(header):
                bom = boms.get(header)
                boms_found.append(bom)
            elif any(header) and header != previous_header:
                values = Bom.default_get(Bom._fields.keys(), with_rec_name=False)

                bom = Bom(**values)
                bom.name = record.name
                boms_to_save.append(bom)
            previous_header = header

            if not bom:
                continue

            for type_ in ('input', 'output'):
                code = getattr(record, type_+'_product')
                if code:
                    with Transaction().set_context(active_test=False):
                        products = Product.search([('code', '=', code)])
                    if len(products) != 1:
                        raise UserError(gettext('importer.single_product_error',
                                product=code))
                    product = products[0]

                    if type_ == 'input':
                        values = BomInput.default_get(BomInput._fields.keys(), with_rec_name=False)
                        line = BomInput(**values)
                    else:
                        values = BomOutput.default_get(BomOutput._fields.keys(), with_rec_name=False)
                        line = BomOutput(**values)
                    line.product = product
                    uom = getattr(record, type_+'_uom')
                    if uom:
                        uom = uoms.get(uom.lower() or product.default_uom)
                    else:
                        uom = product.default_uom
                    line.unit = uom
                    line.quantity = getattr(record, type_+'_quantity')
                    import_hook = getattr(cls, '_import_production_bom_%s_hook' % type_)
                    import_hook(record, line)
                    if type_ == 'input':
                        inputs_to_save.append(line)
                    else:
                        outputs_to_save.append(line)

        for to_save in grouped_slice(boms_to_save):
            Bom.save(list(to_save))

        for to_save in grouped_slice(inputs_to_save):
            BomInput.save(list(to_save))

        for to_save in grouped_slice(outputs_to_save):
            BomOutput.save(list(to_save))
        return boms_to_save or boms_found

    @classmethod
    def import_production_configuration(cls, records):
        pool = Pool()

        Sequence = pool.get("ir.sequence")
        Configuration = pool.get("production.configuration")
        ModelData = pool.get("ir.model.data")

        to_save = []
        for record in records:
            configuration = Configuration(1)

            if record.sequence_padding or record.sequence_number_next:
                sequence = configuration.production_sequence

                if not sequence:
                    sequence = Sequence()
                    sequence.name = "Production"
                    configuration.production_sequence = sequence

                sequence.sequence_type = ModelData.get_id('production', 'sequence_type_production')
                sequence.prefix = record.sequence_prefix
                sequence.suffix = record.sequence_suffix
                sequence.padding = record.sequence_padding
                sequence.number_next = record.sequence_number_next
                sequence.save()

            configuration.save()
            to_save.append(configuration)

        Configuration.save(to_save)

        return to_save
