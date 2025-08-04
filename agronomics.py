import re
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.modules.importer.tools import ImporterModel, Setup, Cache
from trytond.i18n import gettext
from trytond.transaction import Transaction

DNI_REGEX = r'[0-9]+[A-Z]'


class ImporterProductAgronomics(ModelView):
    'Importer Product Agronomics'
    __name__ = 'importer.product.agronomics'

    template_code = fields.Char('Template Code')
    variant_code = fields.Char('Variant Code')
    variant_suffix_code = fields.Char('Variant Suffix Code')
    name = fields.Char('Name')
    description = fields.Char('Description')
    uom = fields.Char('UoM')
    sale_price = fields.Numeric('Sale Price')
    cost_price = fields.Numeric('Cost Price')
    type_ = fields.Char('Type')
    cost_price_method = fields.Char('Cost Price Method')
    supplier = fields.Char('Supplier')
    supplier_code = fields.Char('Supplier Code')
    categories = fields.Char('Categories')
    account_category = fields.Char('Account Category')
    weight = fields.Numeric('Weight (kg)')
    volume = fields.Numeric('Volume (m3)')
    aranzel = fields.Char('Aranzel')
    purchasable = fields.Boolean('Purchasable')
    salable = fields.Boolean('Salable')
    alcohol_content = fields.Char('Alcohol Content')
    brand = fields.Char('Brand')


class ImporterParcel(ImporterModel):
    'Per-parcel Extraction Importer'
    __name__ = 'importer.per_parcel'

    code = fields.Char('Code')
    drawers = fields.Char('Drawers')
    campaign = fields.Integer('Campaign')
    variety = fields.Char('Variety')
    qualification = fields.Char('Qualification')
    plant_numbers = fields.Integer('Number of Plants')
    reg_type = fields.Char('Reg Type')
    area = fields.Char('Area')
    tenure_regime = fields.Char('Tenure Regime')
    dos_name = fields.Char('DOs Name')
    sigpac_data = fields.Char('SIGPAC Data')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        pool = Pool()
        Crop = pool.get('agronomics.crop')
        Date = pool.get('ir.date')
        ProductTaxon = pool.get('product.taxon')

        today = Date.today()
        year = today.year

        cache = Setup.get().cache
        cache.plantations = Cache('agronomics.plantation', 'code',
            required=False)
        cache.parcels = Cache('agronomics.parcel', 'plantation', required=False)
        cache.identifiers = Cache('party.identifier', 'code',
            domain=[('type', '=', 'eu_vat'), ('code', 'like', 'ES%')])
        # We cannot use 'name' as key because it can contain spaces and special chars
        cache.varieties = Cache('product.taxon',
            key=lambda taxon: taxon.name.lower().strip().replace('·', '.'),
            required=False, domain=[('rank', '=', 'variety')])
        cache.ecologicals = Cache('agronomics.ecological', 'name')
        cache.irrigations = Cache('agronomics.irrigation', 'name',
            required=False)
        cache.denominations = Cache('agronomics.denomination_of_origin', 'name',
            required=False)
        cache.beneficiaries = Cache('agronomics.beneficiary',
            key=lambda x: (x.party, x.parcel), required=False)
        cache.max_productions = Cache('agronomics.max.production.allowed',
            'variety')

        crops = Crop.search([('code', '=', str(year))])
        if not crops:
            crop = Crop(code=year, name=year,
                start_date=today.replace(month=1, day=1),
                end_date=today.replace(month=12, day=31))
            crop.save()
            crops = [crop]
        cache.crop = crops[0]

        species = ProductTaxon.search([('rank', '=', 'species')])
        assert species, gettext('importer.msg_no_species_found')
        cache.specie = species[0]

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Beneficiary = pool.get('agronomics.beneficiary')
        Denomination = pool.get('agronomics.denomination_of_origin')
        Enclosure = pool.get('agronomics.enclosure')
        Irrigation = pool.get('agronomics.irrigation')
        Parcel = pool.get('agronomics.parcel')
        Plantation = pool.get('agronomics.plantation')
        Translation = pool.get('ir.translation')

        transaction = Transaction()

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        parcel_to_save = []
        for record in records:
            setup.current_record = record
            enclosure = None
            plantation = None
            parcel = None

            ## Required fields
            required_fields = ['code', 'drawers', 'area', 'sigpac_data',
                'qualification', 'variety']
            missing = {
                field for field in required_fields
                if field not in setup.fields or not getattr(record, field)}
            if not cache.ecologicals.get(record.qualification):
                missing.add('qualification')
            if missing:
                fields_names = [
                    Translation.get_source(f'importer.per_parcel,{field_name}',
                        'field', transaction.language)
                        or getattr(cls, field_name).string
                    for field_name in missing]
                setup.error(gettext('importer.msg_field_required',
                        label='", "'.join(fields_names)))
                continue

            ## Plantation
            plantation = (cache.plantations.get(record.code)
                or Plantation(code=record.code))
            cache.plantations.add(plantation)

            parties = {}
            for string in record.drawers.split('|'):
                parts = string.split('#')
                percentage = parts[-1].replace('%', '').replace(',', '.')
                identifier = cache.identifiers.get(f'ES{parts[0]}')
                if not identifier:
                    continue
                parties[identifier.party] = Decimal(percentage)
            if not parties:
                dnis = re.findall(DNI_REGEX, record.drawers)
                setup.error(gettext('importer.msg_drawers_not_found',
                        dni=', '.join(dnis)))
                continue
            plantation.party = list(parties.keys())[0]

            if 'campaign' in setup.fields and record.campaign:
                plantation.plantation_year = record.campaign

            ## Parcel
            parcel = (
                cache.parcels.get(plantation) or Parcel(plantation=plantation))
            parcel.crop = cache.crop
            parcel.species = cache.specie
            parcel.ecological = cache.ecologicals.get(record.qualification)
            parcel.surface = Decimal(record.area.replace(',', '.'))
            cache.parcels.add(parcel)

            varieties = [label.strip() for label in record.variety.split(',')]
            for variety in varieties:
                variety = cache.varieties.get(variety)
                if variety:
                    break
            else:
                setup.error(gettext('importer.msg_no_varieties_found',
                        taxon='", "'.join(varieties)))
                continue
            parcel.variety = variety

            max_production = cache.max_productions.get(variety)
            if not max_production or not max_production.product:
                setup.error(gettext('importer.msg_no_max_production_found',
                        variety=variety.rec_name))
                continue
            parcel.product = max_production.product.template

            if 'reg_type' in setup.fields and record.reg_type:
                irrigation = (cache.irrigations.get(record.reg_type)
                    or Irrigation(name=record.reg_type))
                cache.irrigations.add(irrigation)
                parcel.irrigation = irrigation

            if 'tenure_regime' in setup.fields and record.tenure_regime:
                parcel.tenure_regime = record.tenure_regime

            if 'dos_name' in setup.fields and record.dos_name:
                prefix = lambda x: f'D.O.P. {x.strip()}'
                parcel.denomination_origin = [
                    cache.denominations.get(prefix(name))
                        or Denomination(name=prefix(name))
                    for name in record.dos_name.split(',')]
                for denomination in parcel.denomination_origin:
                    cache.denominations.add(denomination)

            beneficiaries = []
            for party, percentage in parties.items():
                beneficiary = (cache.beneficiaries.get((party, parcel))
                    or Beneficiary(party=party, parcel=parcel))
                beneficiary.percentage = Decimal(percentage)

                cache.beneficiaries.add(beneficiary)
                beneficiaries.append(beneficiary)
            parcel.beneficiaries = beneficiaries

            if 'plant_numbers' in setup.fields and record.plant_numbers:
                parcel.plant_number = record.plant_numbers

            ## Enclosure
            enclosures = {}
            for data in record.sigpac_data.split(','):
                sigpac = data.strip().split(':')
                enclosure = Enclosure(
                    province_sigpac=int(sigpac[0][:2]),
                    municipality_sigpac=int(sigpac[0][2:]),
                    parcel_sigpac=int(sigpac[1]),
                    enclosure_sigpac=int(sigpac[-1]),
                    plantation=plantation)
                key = f'{sigpac[0]}{sigpac[1]}{sigpac[-1]}{plantation.id}'
                enclosures[key] = enclosure

            for compare in (getattr(plantation, 'enclosures', None) or []):
                province = str(getattr(compare, 'province_sigpac', None) or 0).zfill(2)
                municipality = str(getattr(compare, 'municipality_sigpac', None) or 0).zfill(3)
                key = f'{province}{municipality}{getattr(compare, "parcel_sigpac", None) or 0}{getattr(compare, "enclosure_sigpac", None) or 0}{plantation.id}'
                if key in enclosures:
                    enclosures.pop(key)

            if not getattr(plantation, 'enclosures', None):
                plantation.enclosures = list(enclosures.values())
            else:
                plantation.enclosures += tuple(enclosures.values())

            ## Append objects to save
            to_save.append((plantation, record))
            parcel_to_save.append((parcel, record))

        setup.current_record = None
        cls.importer_save(to_save)
        cls.importer_save(parcel_to_save)
        return [x[0] for x in to_save]


class ImporterMunicipality(ImporterModel):
    'Municipality Importer'
    __name__ = 'importer.sigpac_municipality'

    code = fields.Char('Cadastral Code')
    municipality = fields.Char('Municipality')
    region = fields.Char('Region')
    province = fields.Char('Province')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.municipalities = Cache('agronomics.sigpac.municipality', 'code')

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Municipality = pool.get('agronomics.sigpac.municipality')

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        for record in records:
            setup.current_record = record
            municipality = None

            if 'code' not in setup.fields or not record.code:
                setup.error(gettext('importer.msg_cadastral_code_required'))
                continue

            if cache.municipalities.get(record.code):
                municipality = cache.municipalities.get(record.code)
            else:
                municipality = Municipality(code=record.code)

            if 'region' in setup.fields and record.region:
                municipality.region = record.region.title()
            if 'province' in setup.fields and record.province:
                municipality.province = record.province.title()
            if 'municipality' in setup.fields and record.municipality:
                municipality.municipality = record.municipality.title()

            to_save.append((municipality, record))

        setup.current_record = None
        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'product_agronomics': {
                    'string': 'Product Agronomics',
                    'model': 'importer.product.agronomics',
                    'chunked': True,
                    },
                'agronomics_parcel': {
                    'string': 'Per-parcel Extraction',
                    'model': 'importer.per_parcel',
                    'chunked': True,
                    },
                'agronomics_municipality': {
                    'string': 'SIGPAC Municipality',
                    'model': 'importer.sigpac_municipality',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_product_agronomics(cls, records):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        ProductCategory = pool.get('product.category')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')
        ProductCostPriceMethod = pool.get('product.cost_price_method')

        try:
            ProductSupplier = pool.get('purchase.product_supplier')
            Party = pool.get('party.party')
            parties = dict((x.code, x) for x in Party.search([]))
        except:
            parties = {}

        try:
            TariffCodeRel = pool.get('product-customs.tariff.code')
            TariffCode = pool.get('customs.tariff.code')
            customs = dict((x.code, x) for x in TariffCode.search([]))
        except:
            customs = {}

        try:
            Brand = pool.get('product.brand')
            brands = dict((x.name, x) for x in Brand.search([]))
        except:
            brands = {}

        categories = dict((x.name, x) for x in ProductCategory.search([]))
        uoms = {}
        for uom in Uom.search([]):
            uoms[uom.name.lower()] = uom
            uoms[uom.symbol.lower()] = uom

        products = dict((x.code, x) for x in Product.search([
                    ('code', '!=', None),
                    ('code', '!=', ''),
                    ]))
        templates = dict((x.code, x) for x in Template.search([
                    ('code', '!=', None),
                    ('code', '!=', ''),
                    ]))

        template_default_values = Template.default_get(Template._fields.keys(),
                with_rec_name=False)
        product_default_values = Product.default_get(Product._fields.keys(),
                with_rec_name=False)
        cost_price_methods = ProductCostPriceMethod.get_cost_price_methods()

        to_save = []
        products_to_save = []
        for record in records:
            product = None
            template = None
            if record.variant_code:
                code = record.variant_code
            else:
                code = ((record.template_code or '')
                    + (record.variant_suffix_code or ''))
            product = products.get(code)
            if product:
                template = product.template
            elif record.template_code in templates:
                template = templates.get(record.template_code)

            if not template:
                template = Template(**template_default_values)
                template.products = []

            if not product:
                product = Product(**product_default_values)
                template.products += (product,)
            else:
                products_to_save.append(product)
            to_save.append(template)

            if record.name:
                template.name = record.name
            if record.template_code:
                template.code = record.template_code
            if record.sale_price:
                template.list_price = record.sale_price or Decimal(0)
            uom = None
            if record.uom:
                uom = uoms.get(record.uom.lower() or 'u')
            else:
                uom = uoms.get('u')
                # If we update a product, we dont need to change the uom
                if hasattr(product, 'default_uom') and product.default_uom:
                    uom = None

            if uom:
                template.default_uom = uom
            if record.cost_price_method:
                cost_price_method = record.cost_price_method
                for cpm in cost_price_methods:
                    if cpm[1] == record.cost_price_method:
                        cost_price_method = cpm[0]

                template.cost_price_method = cost_price_method

            if ('account_category' in template._fields and
                    record.account_category):
                acc_category = categories.get(record.account_category)
                if not acc_category:
                    acc_category = ProductCategory()
                    acc_category.name = record.account_category
                    categories[record.account_category] = acc_category
                acc_category.accounting = True
                template.account_category = acc_category

            if 'weight' in template._fields and record.weight:
                template.weight = record.weight
                template.weight_uom = uoms.get('kg')

            if 'volume' in template._fields and record.volume:
                template.volume = record.volume
                template.volume_uom = uoms.get('l')

            if 'tariff_codes' in template._fields and record.aranzel:
                custom = customs.get(record.aranzel)
                if not customs:
                    custom = TariffCode()
                    custom.code = record.aranzel
                    customs[record.aranzel] = customs

                rel = TariffCodeRel()
                rel.tariff_code = custom
                template.tariff_codes = [rel]

            # If product exist the categories are set all new, not updated.
            if record.categories:
                cats = []
                for cat in record.categories.split('|'):
                    category = categories.get(cat)
                    if not category and cat:
                        category = ProductCategory()
                        category.name = cat
                    if category:
                        cats += [category]
                        categories[cat] = category
                template.categories = cats

            if 'product_suppliers' in template._fields and record.purchasable:
                template.purchasable = record.purchasable
                template.purchase_uom = uom

            if 'salable' in template._fields and record.salable:
                template.salable = record.salable
                template.sale_uom = uom

            if parties and record.supplier:
                party = parties.get(record.supplier)
                supplier = ProductSupplier()
                supplier.party = party
                supplier.code = record.supplier_code
                template.product_suppliers = [supplier]

                templates[record.template_code] = template

                if 'brand' in template._fields and record.brand:
                    brand = brands.get(record.brand)
                    if not brand:
                        brand = Brand()
                        brand.name = record.brand
                        brands[record.brand] = brand
                        template.brand = brand

            if record.variant_suffix_code:
                product.suffix_code = record.variant_suffix_code
            if record.cost_price:
                product.cost_price = record.cost_price
            if record.description:
                product.description = record.description
            if ('wine_likely_alcohol_content' in product._fields and
                    record.alcohol_content):
                product.wine_likely_alcohol_content = record.alcohol_content

        ProductCategory.save(categories.values())
        Template.save(to_save)
        Product.save(products_to_save)
        return to_save
