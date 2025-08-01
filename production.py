from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.i18n import gettext
from .tools import ImporterModel, Cache, Setup


class ImporterProductionBom(ImporterModel):
    'Importer Production Bom'
    __name__ = 'importer.production.bom'

    name = fields.Char('Name')
    input_product = fields.Char('Product Input')
    input_quantity = fields.Float('Product Input Quantity')
    input_uom = fields.Char('Product Input UoM')
    output_product = fields.Char('Product Output')
    output_quantity = fields.Float('Product Output Quantity')
    output_uom = fields.Char('Product Output UoM')

    @classmethod
    def importer_start(cls):
        super().importer_start()

        cache = Setup.get().cache
        cache.products = Cache('product.product', 'code')
        cache.uoms_name = Cache('product.uom', 'name')
        cache.uoms_symbol = Cache('product.uom', 'symbol')
        cache.boms = Cache('production.bom', 'name')

    def importer_header(self, importing=True):
        return (self.name)

    @classmethod
    def _import_production_bom_input_hook(cls, record, input):
        pass

    @classmethod
    def _import_production_bom_output_hook(cls, record, output):
        pass

    @classmethod
    def _import_production_bom_hook(cls, record, boom):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Bom = pool.get('production.bom')
        BomInput = pool.get('production.bom.input')
        BomOutput = pool.get('production.bom.output')


        setup = Setup.get()
        cache = setup.cache

        bom = None
        boms_to_save = []
        inputs_to_save = []
        outputs_to_save = []
        to_save_products = []
        previous_header = None
        for record in records:
            setup.current_record = record

            header = record.importer_header()
            if any(header) and header != previous_header:
                previous_header = header
                if 'name' in setup.fields:
                    bom = cache.boms.get(record.name)
                    if not bom:
                        values = Bom.default_get(Bom._fields.keys(),
                            with_rec_name=False)
                        bom = Bom(**values)
                        bom.name = record.name
                        cls._import_production_bom_hook(record, bom)
                        boms_to_save.append((bom, record))
            if not bom:
                continue
            for type_ in ('input', 'output'):
                if type_+'_product' in setup.fields:
                    product = cache.products.get(getattr(record, type_+'_product'))
                    if not product:
                        setup.error(gettext(
                            'importer.msg_production_bom_product_not_found',
                            product=getattr(record, type_+'_product')))
                        continue
                    if not product.template.producible:
                        product.template.producible = True
                        to_save_products.append((product.template, record))

                    if type_ == 'input':
                        values = BomInput.default_get(BomInput._fields.keys(), with_rec_name=False)
                        line = BomInput(**values)
                    else:
                        values = BomOutput.default_get(BomOutput._fields.keys(), with_rec_name=False)
                        line = BomOutput(**values)
                    line.bom = bom
                    line.product = product
                    uom = product.default_uom
                    if type_+'_uom' in setup.fields:
                        uom = cache.uoms_name.get(getattr(record, type_+'_uom').lower())
                        if not uom:
                            uom = cache.uoms_symbol.get(getattr(record, type_+'_uom').lower())
                        if not uom:
                            setup.error(gettext(
                                'importer.msg_production_bom_uom_not_found',
                                uom=getattr(record, type_+'_uom')))
                    line.unit = uom
                    line.quantity = getattr(record, type_+'_quantity')

                    if type_ == 'input':
                        cls._import_production_bom_input_hook(record, line)
                        inputs_to_save.append((line, record))
                    else:
                        cls._import_production_bom_output_hook(record, line)
                        outputs_to_save.append((line, record))
        cls.importer_save(to_save_products)
        cls.importer_save(boms_to_save)
        cls.importer_save(inputs_to_save)
        cls.importer_save(outputs_to_save)
        return [x[0] for x in boms_to_save]


class ImporterProductionConfiguration(ImporterModel):
    'Importer Production Configuration'
    __name__ = 'importer.production.configuration'

    sequence_prefix = fields.Char("Sequence prefix")
    sequence_suffix = fields.Char("Sequence suffix")
    sequence_padding = fields.Integer("Sequence padding")
    sequence_number_next = fields.Integer("Sequence number next")

    @classmethod
    def _import_production_configuration_hook(cls, record, configuration):
        pass

    @classmethod
    def importer_import(cls, records):
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
            cls._import_production_configuration_hook(record, configuration)
            configuration.save()
            to_save.append(configuration)
        Configuration.save(to_save)
        return to_save


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'production_bom': {
                    'string': 'Production BOM',
                    'model': 'importer.production.bom',
                    'chunked': False,
                    },
                'production_configuration': {
                    'string': 'Production configuration',
                    'model': 'importer.production.configuration',
                    'chunked': True,
                    },
                })
        return methods
