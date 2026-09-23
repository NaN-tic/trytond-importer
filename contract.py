from trytond.model import fields
from trytond.pool import Pool, PoolMeta

from .tools import Cache, ImporterModel, Setup


class ImporterContract(ImporterModel):
    'Contract and contract line import record.'
    __name__ = 'importer.contract'

    number = fields.Char('Contract Number')
    reference = fields.Char('Contract Reference')
    company = fields.Char('Company')
    currency = fields.Char('Currency')
    party = fields.Char('Party')
    party_code = fields.Char('Party Code')
    start_period_date = fields.Date('Start Period Date')
    first_invoice_date = fields.Date('First Invoice Date')
    payment_term = fields.Char('Payment Term')
    freq = fields.Char('Frequency')
    interval = fields.Integer('Interval')

    service = fields.Char('Service')
    description = fields.Text('Line Description')
    unit_price = fields.Numeric('Line Unit Price', digits=(16, 2))
    quantity = fields.Float('Line Quantity')
    start_date = fields.Date('Line Start Date')
    end_date = fields.Date('Line End Date')
    sequence = fields.Integer('Line Sequence')
    line_type = fields.Char('Line Type')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.contracts = Cache('contract', ['number', 'reference'],
            required=False, duplicates='abort-on-use')
        cache.services = Cache('contract.service', 'name',
            required=False, duplicates='abort-on-use')
        cache.product_templates = Cache('product.template', 'name',
            required=False)
        cache.companies = Cache('company.company', 'rec_name', required=False)
        cache.currencies = Cache('currency.currency', ['name', 'symbol'],
            required=False)
        cache.parties_by_code = Cache('party.party', 'code',
            required=False, duplicates='abort-on-use')
        cache.parties_by_name = Cache('party.party', 'name',
            required=False, duplicates='abort-on-use')
        cache.payment_terms = Cache('account.invoice.payment_term', 'name',
            required=False)
        cache.parties_to_save = []
        try:
            cache.line_types = Cache('contract.line.type', 'name',
                required=False)
        except KeyError:
            cache.line_types = None

    @classmethod
    def importer_contract_hook(cls, record, contract, line):
        'Hook for modules adding contract or line fields.'

    @classmethod
    def _get_contract(cls, record, cache):
        keys = [record.number, record.reference]
        keys = [key for key in keys if key]
        key = keys[0] if keys else None
        contract = None
        for key in keys:
            contract = cache.contracts.get(key)
            if contract:
                break
        if contract:
            return contract
        if not key:
            record.importer_error(
                'A contract number or reference is required.')
            return

        Contract = Pool().get('contract')
        values = Contract.default_get(Contract._fields.keys(),
            with_rec_name=False)
        contract = Contract(**values)

        company = cache.companies.get(record.company) if record.company else None
        if company:
            contract.company = company
        else:
            company = contract.company
        currency = cache.currencies.get(record.currency) \
            if record.currency else None
        if currency:
            contract.currency = currency
        else:
            currency = contract.currency
        party = cls._get_party(record, cache)
        if not party:
            record.importer_error(
                'Party is required to create contract "%s".' % key)
        if not record.start_period_date or not record.first_invoice_date:
            record.importer_error(
                'Contract "%s" requires start and first invoice dates.'
                % key)
        if not all((company, currency, party, record.start_period_date,
                record.first_invoice_date)):
            return
        contract.number = record.number
        contract.reference = record.reference
        contract.party = party
        contract.start_period_date = record.start_period_date
        contract.first_invoice_date = record.first_invoice_date
        contract.freq = record.freq or 'monthly'
        contract.interval = record.interval or 1
        if record.payment_term:
            payment_term = cls._get_payment_term(record, cache)
            if payment_term:
                contract.payment_term = payment_term
        cache.contracts[key] = contract
        for key in keys:
            cache.contracts[key] = contract
        return contract

    @classmethod
    def _get_payment_term(cls, record, cache):
        payment_term = cache.payment_terms.get(record.payment_term)
        if payment_term:
            return payment_term
        try:
            PaymentTerm = Pool().get('account.invoice.payment_term')
            PaymentTermLine = Pool().get('account.invoice.payment_term.line')
        except KeyError:
            record.importer_error(
                'Payment term support requires the account_invoice module.')
            return
        payment_term = PaymentTerm(name=record.payment_term)
        payment_term.lines = [PaymentTermLine(type='remainder')]
        payment_term.save()
        cache.payment_terms[record.payment_term] = payment_term
        return payment_term

    @classmethod
    def _get_party(cls, record, cache):
        Party = Pool().get('party.party')
        code = getattr(record, 'party_code', None) or None
        name = getattr(record, 'party_name', None)
        party = cache.parties_by_code.get(code) if code else None
        if not party and record.party:
            party = cache.parties_by_code.get(record.party)
            if not party:
                party = cache.parties_by_name.get(record.party)
                if not name:
                    name = record.party
        if not party and name:
            party = cache.parties_by_name.get(name)
        if party:
            return party
        if not name and not code and not record.party:
            return

        party = Party()
        party.code = code
        party.name = name or record.party
        vat = getattr(record, 'party_vat', None)
        if vat:
            PartyIdentifier = Pool().get('party.identifier')
            identifier = PartyIdentifier(code=vat.strip().upper())
            if identifier.code.startswith('ES'):
                identifier.type = 'eu_vat'
            party.identifiers = [identifier]
        cache.parties_to_save.append(party)
        if party.code:
            cache.parties_by_code[party.code] = party
        if party.name:
            cache.parties_by_name[party.name] = party
        return party

    @classmethod
    def _get_line_type(cls, record, cache):
        if not record.line_type:
            return None
        line_types = cache.line_types
        if line_types is None:
            record.importer_error(
                'Line type support requires the contract_document module.')
            return None
        line_type = line_types.get(record.line_type)
        if line_type:
            return line_type
        LineType = Pool().get('contract.line.type')
        line_type = LineType(name=record.line_type)
        line_type.save()
        cache.line_types[record.line_type] = line_type
        return line_type

    @classmethod
    def _get_service(cls, record, cache):
        if not record.service:
            return
        service = cache.services.get(record.service)
        if service:
            return service

        ProductTemplate = Pool().get('product.template')
        Product = Pool().get('product.product')
        Uom = Pool().get('product.uom')
        template = cache.product_templates.get(record.service)
        if not template or template.type != 'service':
            units = Uom.search([('name', '=', 'Unit')], limit=1)
            if not units:
                record.importer_error(
                    'Unit of Measure "Unit" was not found for service '
                    '"%s".' % record.service)
                return
            template = ProductTemplate(name=record.service, type='service',
                default_uom=units[0], list_price=0)
            template.save()
            cache.product_templates[record.service] = template
        if not template.products:
            product = Product(template=template)
            product.save()
        else:
            product, = template.products
        Service = Pool().get('contract.service')
        service = Service(name=record.service, product=product)
        service.save()
        cache.services[record.service] = service
        return service

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Line = pool.get('contract.line')
        setup = Setup.get()
        cache = setup.cache
        parties_to_save = []
        contracts_to_save = []
        lines_to_save = []
        saved_contracts = set()

        for record in records:
            setup.current_record = record
            contract = cls._get_contract(record, cache)
            if not contract:
                continue

            for field in ('reference', 'start_period_date',
                    'first_invoice_date', 'freq', 'interval'):
                if field in setup.fields and getattr(record, field) is not None:
                    setattr(contract, field, getattr(record, field))

            line = cls._find_line(record, contract)
            if not line:
                values = Line.default_get(Line._fields.keys(),
                    with_rec_name=False)
                line = Line(**values)
                line.contract = contract
            if 'service' in setup.fields and record.service:
                line.service = cls._get_service(record, cache)
                if not line.service:
                    record.importer_error(
                        'Service "%s" was not found.' % record.service)
                    continue
            if 'description' in setup.fields and record.description is not None:
                line.description = record.description
            if 'unit_price' in setup.fields and record.unit_price is not None:
                line.unit_price = record.unit_price
            if 'quantity' in setup.fields and record.quantity is not None:
                line.quantity = record.quantity
            if 'start_date' in setup.fields and record.start_date is not None:
                line.start_date = record.start_date
            if 'end_date' in setup.fields and record.end_date is not None:
                line.end_date = record.end_date
            if 'sequence' in setup.fields and record.sequence is not None:
                line.sequence = record.sequence
            if 'line_type' in setup.fields and record.line_type:
                line_type = cls._get_line_type(record, cache)
                if line_type and hasattr(line, 'line_type'):
                    line.line_type = line_type

            cls.importer_contract_hook(record, contract, line)
            print(
                'Contract importer line ready: contract=%r, line_id=%r, '
                'asset=%r, service=%r, description=%r, unit_price=%r, '
                'quantity=%r, sequence=%r' % (
                    contract.number or contract.reference, line.id,
                    (line.asset.rec_name if getattr(line, 'asset', None)
                        else None),
                    (line.service.rec_name if getattr(line, 'service', None)
                        else None),
                    getattr(line, 'description', None),
                    getattr(line, 'unit_price', None),
                    getattr(line, 'quantity', None),
                    getattr(line, 'sequence', None)))
            if id(contract) not in saved_contracts:
                contracts_to_save.append((contract, record))
                saved_contracts.add(id(contract))
            lines_to_save.append((line, record))

        parties_to_save = [(party, None) for party in cache.parties_to_save]
        print('Contract importer saving: parties=%d, contracts=%d, lines=%d'
            % (len(parties_to_save), len(contracts_to_save),
                len(lines_to_save)))
        cls.importer_save(parties_to_save)
        cls.importer_save(contracts_to_save)
        cls.importer_save(lines_to_save)
        return [record for record, _ in parties_to_save + contracts_to_save
            + lines_to_save]

    @staticmethod
    def _find_line(record, contract):
        contract_lines = getattr(contract, 'lines', ())
        if record.sequence is not None:
            lines = [line for line in contract_lines
                if line.sequence == record.sequence]
            if len(lines) == 1:
                return lines[0]
            if len(lines) > 1:
                record.importer_error(
                    'More than one contract line has sequence %s.'
                    % record.sequence)
                return None
        if record.service:
            lines = [line for line in contract_lines
                if line.service and line.service.name == record.service]
            if len(lines) == 1:
                return lines[0]
        return None


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
            'contract': {
                'string': 'Contract',
                'model': 'importer.contract',
            },
        })
        return methods
