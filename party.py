from datetime import timedelta
from trytond.tools.email_ import validate_email
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from stdnum import get_cc_module
from trytond.exceptions import UserError
from trytond.i18n import gettext
from .tools import ImporterModel, Cache, Setup


class ImporterPartyConfiguration(ModelView):
    'Importer Party Configuration'
    __name__ = 'importer.party.configuration'

    language_code = fields.Char('Language Code')
    sequence_prefix = fields.Char("Sequence prefix")
    sequence_suffix = fields.Char("Sequence suffix")
    sequence_padding = fields.Integer("Sequence Padding")
    sequence_number_next = fields.Integer("Sequence Number Next")


class ImporterParty(ImporterModel):
    'Importer Party'
    __name__ = 'importer.party'

    company = fields.Char('Company',
        help="Company field can be used to set company-dependent fields."
        "Better sort records by company prior to import for better "
        "performance.")
    code = fields.Char('Code')
    name = fields.Char('Name')
    trade_name = fields.Char('Trade Name')
    language = fields.Char('Language')
    street = fields.Char('Street')
    postal_code = fields.Char('Postal Code')
    city = fields.Char('City')
    subdivision = fields.Char('Subdivision')
    country = fields.Char('Country')
    shipment_street = fields.Char('Shipment Street')
    shipment_postal_code = fields.Char('Shipment Postal Code')
    shipment_city = fields.Char('Shipment City')
    shipment_subdivision = fields.Char('Shipment Subdivision')
    shipment_country = fields.Char('Shipment Country')
    phone = fields.Char('Phone')
    fax = fields.Char('Fax')
    email = fields.Char('E-Mail')
    website = fields.Char('Website')
    categories = fields.Char('Categories')
    customer_payment_term = fields.Char('Customer Payment Term')
    customer_payment_type = fields.Char('Customer Payment Type')
    supplier_payment_term = fields.Char('Supplier Payment Term')
    supplier_payment_type = fields.Char('Supplier Payment Type')
    bank_account = fields.Char('Iban')
    customer_payment_days = fields.Char('Customer Payment days')
    supplier_payment_days = fields.Char('Supplier Payment days')
    vat = fields.Char('Vat')
    party_relation = fields.Char('Party Relation')
    type_of_relation = fields.Char('Type of relation')
    note = fields.Char('Note')

    @classmethod
    def importer_start(cls):
        pool = Pool()
        Type = pool.get('party.address.subdivision_type')

        super().importer_start()

        cache = Setup.get().cache
        cache.parties = Cache('party.party', 'code', required=False)
        cache.companies = Cache('company.company', key=lambda x: x.party.name)
        cache.banks = Cache('bank', key=lambda x: x.bank_code.zfill(4))
        cache.bank_accounts = Cache('bank.account.number', 'number_compact')
        cache.payment_terms = Cache('account.invoice.payment_term', 'name')
        cache.payment_types = Cache('account.payment.type', key=lambda x: (x.name.lower(), x.kind))
        cache.relations = Cache('party.relation.type', 'name')
        cache.tax_rules = Cache('account.tax.rule', 'name')
        cache.agents = Cache('commission.agent', key=lambda x: (x.party.code
            and x.party.code.lower(), x.plan and x.plan.name))
        cache.agents_no_plan = Cache('commission.agent', key=lambda x:
            x.party.name and x.party.name.lower())
        cache.inco_terms = Cache('incoterm', 'code')
        cache.languages = Cache('ir.lang', 'code')
        cache.categories = Cache('party.category', 'name')
        cache.countries = Cache('country.country', 'code', unaccent=True)
        cache.subdivisions = {}
        for country in cache.countries.values():
            types = Type.get_types(country)
            cache.subdivisions[country] = Cache('country.subdivision', 'name', domain=[
                ('country', '=', country.id),
                ('type', 'in', types),
                ], unaccent=True)
        cache.postal_codes = Cache('country.subdivision', 'code')

    def importer_context(self):
        res = super().importer_context()
        setup = Setup.get()
        if 'company' in setup.fields and self.company:
            company = setup.cache.companies.get(self.company)
            if company:
                res['company'] = company.id
        return res

    @classmethod
    def importer_party(cls, record, party):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        PartyIdentifier = pool.get('party.identifier')
        PartyCategory = pool.get('party.category')
        BankAccount = pool.get('bank.account')
        AccountNumber = pool.get('bank.account.number')
        Note = pool.get('ir.note')

        try:
            PaymentTerm = pool.get('account.invoice.payment_term')
            PaymentTermLine = pool.get('account.invoice.payment_term.line')
        except KeyError:
            PaymentTerm = None
            PaymentTermLine = None
        try:
            PaymentType = pool.get('account.payment.type')
        except KeyError:
            PaymentType = None
        try:
            Relation = pool.get('party.relation')
        except KeyError:
            Relation = None

        setup = Setup.get()
        cache = setup.cache

        company = Transaction().context.get('company')
        vats = {}
        to_save = []
        to_set_bank_accounts = []
        categories_to_save = []
        notes_to_save = []
        relations_to_save = {}
        for record in records:
            setup.current_record = record
            party = None
            if record.code:
                party = cache.parties.get(record.code)

            if not party:
                party = Party()
                party.code = record.code
                cache.parties[record.code] = party

            to_save.append((party, record))

            if 'name' in setup.fields:
                party.name = record.name
            if 'trade_name' in setup.fields:
                party.trade_name = record.trade_name
            if 'supplier' in setup.fields:
                party.supplier = record.supplier
            if 'customer' in setup.fields:
                party.customer = record.customer

            # TODO allow days, hours... cast_value format
            if ('supplier_lead_time' in setup.fields
                    and record.supplier_lead_time):
                party.supplier_lead_time = timedelta(
                    days=record.supplier_lead_time)

            addresses = []
            address = Address()
            if hasattr(Address, 'invoice'):
                address.invoice = True
            address.street = record.street
            address.postal_code = record.postal_code
            address.city = record.city
            country = cache.countries.get(record.country)
            if not country:
                country = cache.countries.get('ES')
            address.country = country
            if hasattr(Address, 'delivery'):
                address.delivery = record.delivery_address
            if hasattr(Address, 'invoice'):
                address.invoice = record.invoice_address

            subdivision_error = None
            cs = cache.subdivisions.get(country)

            if cs and record.subdivision:
                if record.subdivision in cs:
                    address.subdivision = cs.get(record.subdivision)
                else:
                    subdivision_error = gettext('importer.msg_subdivision_not_found',
                        subdivision=record.subdivision,
                        country=country.name)

            if (not getattr(address, 'subdivision', None)
                    and country and country.code == 'ES'
                    and record.postal_code):
                code = cache.postal_codes.get(record.postal_code)
                if code:
                    address.subdivision = code.subdivision

            if not getattr(address, 'subdivision', None) and subdivision_error:
                setup.error(subdivision_error, record)

            addresses.append(address)
            if 'language' in setup.fields:
                party.lang = cache.languages.get(record.language)

            if (record.shipment_street or record.shipment_postal_code or
                    record.shipment_city or record.shipment_subdivision or
                    record.shipment_country):
                shipment_address = Address()
                if hasattr(Address, 'shipment'):
                    shipment_address.shipment = True
                shipment_address.street = record.shipment_street
                shipment_address.postal_code = record.shipment_postal_code
                shipment_address.city = record.shipment_city
                country = cache.countries.get(record.shipment_country)
                shipment_address.country = country


                subdivision_error = None
                cs = cache.subdivisions.get(country)
                if cs and record.shipment_subdivision:
                    if record.subdivision in cs:
                        shipment_address.subdivision = cs.get(record.subdivision)
                    else:
                        subdivision_error = gettext('importer.msg_subdivision_not_found',
                            subdivision=record.subdivision,
                            country=country.name)

                if (not getattr(shipment_address, 'subdivision', None)
                        and country and country.code == 'ES'
                        and record.postal_code):
                    code = cache.postal_codes.get(record.postal_code)
                    if code:
                        shipment_address.subdivision = code.subdivision

                if not getattr(shipment_address, 'subdivision', None) and subdivision_error:
                    setup.error(subdivision_error, record)

                addresses.append(shipment_address)

            party.addresses = addresses

            contacts = []
            if record.website:
                contact = ContactMechanism()
                contact.type = 'website'
                contact.value = record.website
                contacts.append(contact)
            if record.phone:
                phones = [x.strip() for x in record.phone.split('/')]
                for phone in phones:
                    contact = ContactMechanism()
                    contact.type = 'phone'
                    contact.value = phone
                    contacts.append(contact)
            if record.email:
                emails = [x.strip().lower() for x in record.email.split('/')]
                for email in emails:
                    contact = ContactMechanism()
                    try:
                        validate_email(email)
                        contact.type = 'email'
                    except:
                        contact.type = 'other'
                    contact.value = email
                    contacts.append(contact)
            if record.fax:
                faxes = [x.strip() for x in record.fax.split('/')]
                for fax in faxes:
                    contact = ContactMechanism()
                    contact.type = 'fax'
                    contact.value = fax
                    contacts.append(contact)
            party.contact_mechanisms = contacts

            payment_term = cache.payment_terms.get(record.customer_payment_term)
            if (record.customer_payment_term and not payment_term):
                payment_term = PaymentTerm(name=record.customer_payment_term)
                payment_term.lines = [PaymentTermLine(type='remainder')]
                payment_term.save()
                cache.payment_terms[record.customer_payment_term] = payment_term

            if payment_term:
                party.customer_payment_term = payment_term

            payment_term = cache.payment_terms.get(record.supplier_payment_term)
            if (record.supplier_payment_term and not payment_term):
                payment_term = PaymentTerm(name=record.supplier_payment_term)
                payment_term.lines = [PaymentTermLine(type='remainder')]
                payment_term.save()
                cache.payment_terms[record.supplier_payment_term] = payment_term

            if payment_term:
                party.supplier_payment_term = payment_term

            customer_payment_type = None
            if record.customer_payment_type:
                key = (record.customer_payment_type.lower(), 'receivable')
                if not key in cache.payment_types:
                    key = (record.customer_payment_type.lower(), 'both')
                customer_payment_type = cache.payment_types.get(key)

            if (record.customer_payment_type and
                    not customer_payment_type):
                customer_payment_type = PaymentType(
                    name=record.customer_payment_type)
                customer_payment_type.kind = 'receivable'
                customer_payment_type.account_bank = 'none'
                customer_payment_type.save()
                cache.payment_types[(record.customer_payment_type,
                    'receivable')]=customer_payment_type

            if customer_payment_type and record.customer_payment_type:
                party.customer_payment_type = customer_payment_type

            supplier_payment_type = None
            if record.supplier_payment_type:
                key = (record.supplier_payment_type.lower(), 'payable')
                if not key in cache.payment_types:
                    key = (record.supplier_payment_type.lower(), 'both')
                supplier_payment_type = cache.payment_types.get(key)
            if (record.supplier_payment_type
                    and not supplier_payment_type):
                supplier_payment_type = PaymentType(
                    name=record.supplier_payment_type)
                supplier_payment_type.kind = 'payable'
                supplier_payment_type.account_bank = 'none'
                supplier_payment_type.save()
                cache.payment_types[(record.supplier_payment_type,
                    'payable')] = supplier_payment_type
            if supplier_payment_type and record.supplier_payment_type:
                party.supplier_payment_type = supplier_payment_type

            if (record.customer_payment_days
                    and 'customer_payment_days' in setup.fields):
                party.customer_payment_days = record.customer_payment_days

            if (record.supplier_payment_days
                    and 'supplier_payment_days' in setup.fields):
                party.supplier_payment_days = record.supplier_payment_days

            if record.vat:
                vat = "%s%s" % (record.country, record.vat)
                vat_type = 'eu_vat'
                if vat in vats:
                    vat_type = None

                module = get_cc_module(*['eu', 'vat'])
                if not module.is_valid(vat):
                    vat_type = None

                party_identifier = PartyIdentifier()
                party_identifier.type = vat_type
                party_identifier.code = vat
                party.identifiers = (party_identifier,)
                vats[vat] = record.code

            if record.categories:
                cats = []
                for cat in record.categories.split('|'):
                    category = cache.categories.get(cat)
                    if not category and cat:
                        category = PartyCategory()
                        category.name = cat
                        categories_to_save.append((category, record))
                    if category:
                        cats += [category]
                        cache.categories[cat] = category

                party.categories = cats

            if 'customer_tax_rule' in setup.fields:
                party.customer_tax_rule = cache.tax_rules.get(
                    record.customer_tax_rule)
            if 'supplier_tax_rule' in setup.fields:
                party.supplier_tax_rule = cache.tax_rules.get(
                    record.supplier_tax_rule)

            if record.bank_account and 'bank_accounts' in setup.fields:
                Currency = pool.get('currency.currency')
                cache.currencies = dict([(x.code, x) for x in Currency.search([])])
                party.bank_accounts = []
                for account in record.bank_account.split('|'):
                    if (',') in account:
                        iban, currency_code = account.split(',')
                    else:
                        iban = account
                        currency_code = 'EUR'
                    iban = iban.replace(" ", "")
                    currency = cache.currencies.get(currency_code)
                    if len(iban) < 8:
                        raise UserError(gettext('importer.wron_iban',
                            iban_= iban))

                    bank_code = iban[4:8]
                    bank = cache.banks.get(bank_code)
                    if not bank:
                        raise UserError(gettext('importer.bank_not_found',
                            iban=iban))
                    bank_account = BankAccount()
                    bank_account.bank = bank
                    bank_account.currency = currency
                    account_number = AccountNumber()
                    account_number.account = bank_account
                    account_number.type = 'iban'
                    account_number.number = iban
                    cache.bank_accounts[iban]=account_number
                    bank_account.numbers = [account_number]
                    party.bank_accounts += (bank_account,)

                to_set_bank_accounts.append(party)


            if 'default_payable_company_bank_account' in setup.fields:
                party.payable_company_bank_account = cache.bank_accounts.get(
                    record.default_payable_company_bank_account)

            if 'default_receivable_company_bank_account' in setup.fields:
                party.receivable_company_bank_account = cache.bank_accounts.get(
                    record.default_receivable_company_bank_account)

            if 'agent' in setup.fields and record.agent:
                new_agents = []
                CommissionAgentSelection = pool.get('commission.agent.selection')
                for agent in record.agent.split('|'):
                    if ',' in agent:
                        agent, plan = agent.split(',')
                        key = (agent, plan)
                        com_a = cache.agents.get((key))
                    else:
                        com_a = cache.agents_no_plan.get(agent)
                        plan = None

                    if not com_a:
                        setup.error(gettext('importer.agent_not_found',
                            agent=agent, plan=plan),
                            record)
                    com_agen_sel = CommissionAgentSelection()
                    com_agen_sel.agent = com_a
                    com_agen_sel.company = company
                    new_agents.append(com_agen_sel)
                party.agents = new_agents


            if hasattr(Party, 'sii_identifier_type'):
                if record.sii_identifier_type != 'None':
                    party.sii_identifier_type = record.sii_identifier_type

            if 'incoterm' in setup.fields:
                party.incoterm = cache.incoterms.get(record.incoterm_name)
                party.on_change_incoterm()
                party.incoterm_place = record.incoterm_place
            if 'purchase_incoterm' in setup.fields:
                party.purchase_incoterm = cache.incoterms.get(
                    record.incoterm_purchase_name)
                party.on_change_purchase_incoterm()
                party.purchase_incoterm_place = record.incoterm_purchase_place

            if 'relations' in setup.fields and record.party_relation:
                related = cache.parties.get(record.party_relation)
                if related:
                    type_relation = cache.relations.get(record.type_of_relation)
                    party_relation = Relation()
                    party_relation.to = related
                    party_relation.type = type_relation
                    relations_to_save[party.code] = party_relation

            if record.note:
                note = Note()
                note.resource = party
                note.message = record.note
                notes_to_save.append((note, record))

            cls.importer_party(record, party)

        cache.current_record = None
        cls.importer_save(categories_to_save)
        cls.importer_save(to_save)
        # If party has not been saved, do not try to save its notes
        cls.importer_save([x for x in notes_to_save if x[0].resource.id])

        if 'payable_bank_account' in setup.fields:
            # These fields must be set after party has been saved as only
            # accounts in bank_accounts can be used
            for party in to_set_bank_accounts:
                if not party.bank_accounts:
                    continue
                party.payable_bank_account = party.bank_accounts[0]
                party.receivable_bank_account = party.bank_accounts[0]
            cls.importer_save(to_save)

        if 'relations' in setup.fields:
            new_parties = dict((x.code, x) for x in to_save)
            rel_save = []
            for code, relation in relations_to_save.items():
                relation.from_ = new_parties.get(code)
                rel_save.append(relation)
            cls.importer_save(rel_save)
        return [x[0] for x in to_save]

class ImporterPartyAddress(ImporterModel):
    'Importer Address'
    __name__ = 'importer.party.address'

    city = fields.Char('City')
    country = fields.Char('Country')
    name = fields.Char('Name')
    subdivision = fields.Char('Address Subdivision')
    street = fields.Char('Street Address')

    @classmethod
    def importer_start(cls):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        Address = pool.get('party.address')
        to_save = []
        for record in records:
            address = Address()
            found_countries = None
            if record.country.isnumeric():
                found_countries = Country.search([('id', '=', record.country)], limit=1)
            else:
                found_countries = Country.search([('name', '=', record.country)], limit=1)
            if  found_countries:
                address.country = found_countries[0]
            found_subdivision = None
            if record.subdivision.isnumeric():
                found_subdivision = Subdivision.search([('id', '=', record.subdivision)], limit=1)
            else:
                Subdivision.search([('code', '=', record.subdivision)], limit=1)
                if not found_subdivision:
                    Subdivision.search([('name', '=', record.subdivision)], limit =1)
            if found_subdivision:
                address.subdivision = found_subdivision[0]
            address.street = record.street
            address.name = record.name
            to_save.append((address, record))
        cls.importer_save(to_save)
        return [x[0] for x in to_save]



class ImporterPartyInvoiceDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    invoice_address = fields.Boolean('Invoice Address')


class ImporterPartyStockDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    delivery_address = fields.Boolean('Delivery Address')


class ImporterCustomerDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    customer = fields.Boolean('Customer')


class ImporterSupplierDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    supplier = fields.Boolean('Supplier')


class ImporterPurchaseDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    supplier_lead_time = fields.Integer('Supplier Lead Time (days)')


class ImporterCommissionDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    agent = fields.Char('Agent (code)')


class ImporterAccountDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    customer_tax_rule = fields.Char('Customer Tax Rule')
    supplier_tax_rule = fields.Char('Supplier Tax Rule')


class ImporterCompanyBankDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    default_payable_company_bank_account = fields.Char(
        'Default payable company  Bank Account')
    default_receivable_company_bank_account = fields.Char(
        'Default receivable company Bank Account')


class ImporterIncotermDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    incoterm_name = fields.Char('Incoterm Name')
    incoterm_place = fields.Char('Incoterm Place')


class ImporterIncotermPurchaseDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    incoterm_purchase_name = fields.Char('Incoterm Purchase Name')
    incoterm_purchase_place = fields.Char('Incoterm Purchase Place')


class ImporterAEATSIIDepends(metaclass=PoolMeta):
    __name__ = 'importer.party'
    sii_identifier_type = fields.Char('SII Identification Type')


class ImporterContactMechanism(ModelView):
    'Importer Contact Method'
    __name__ = 'importer.party.contact_mechanism'
    party = fields.Char("Party")
    type = fields.Char("Type")
    value = fields.Char("Value")
    name = fields.Char("Name")
    language = fields.Char("Language")


class ImporterContactMechanismInvoiceDepends(metaclass=PoolMeta):
    __name__ = 'importer.party.contact_mechanism'
    invoice = fields.Boolean("Invoice")


class ImporterContactMechanismStockDepends(metaclass=PoolMeta):
    __name__ = 'importer.party.contact_mechanism'
    delivery = fields.Boolean("Delivery")


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'party': {
                    'string': 'Party',
                    'model': 'importer.party',
                    'chunked': True,
                    },
                'contact_mechanism': {
                    'string': 'Contact Mechanism',
                    'model': 'importer.party.contact_mechanism',
                    'chunked': True,
                    },
                'party_configuration': {
                    'string': 'Party configuration',
                    'model': 'importer.party.configuration',
                    'chunked': True,
                    },
                'party_address': {
                    'string': 'Address',
                    'model': 'importer.party.address',
                    'chunked': True,
                },
                })
        return methods

    @classmethod
    def import_contact_mechanism(cls, records):
        pool = Pool()
        Party = pool.get('party.party')
        Lang = pool.get('ir.lang')
        ContactMechanism = pool.get('party.contact_mechanism')
        ContactMechanismLanguage = pool.get('party.contact_mechanism.language')

        company = Transaction().context.get('company')
        languages = dict([(x.code, x) for x in Lang.search([])])
        parties = dict([(x.code, x) for x in Party.search([])])

        to_save_cm = []
        to_save_cml = []
        for record in records:
            if not record.party in parties:
                raise UserError(
                    gettext('importer.party_not_found',
                        party=record.party))
            cm = ContactMechanism()
            cm.party = parties[record.party]
            cm.name = record.name
            cm.type = record.type
            cm.value = record.value

            if hasattr(ContactMechanism, 'invoice'):
                cm.invoice = False
                if record.invoice:
                    cm.invoice = record.invoice

            if hasattr(ContactMechanism, 'delivery'):
                cm.delivery = False
                if record.delivery:
                    cm.delivery = record.delivery

            to_save_cm.append(cm)
            if record.language:
                cml = ContactMechanismLanguage()
                cml.contact_mechanism = cm
                cml.language = languages.get(record.language)
                cml.company = company
                to_save_cml.append(cml)

        ContactMechanism.save(to_save_cm)
        ContactMechanismLanguage.save(to_save_cml)
        return to_save_cm

    @classmethod
    def import_party_configuration(cls, records):
        pool = Pool()

        Sequence = pool.get("ir.sequence")
        Configuration = pool.get("party.configuration")
        Lang = pool.get("ir.lang")
        ModelData = pool.get("ir.model.data")

        to_save = []
        for record in records:
            configuration = Configuration(1)

            if record.sequence_padding or record.sequence_number_next:
                sequence = configuration.party_sequence

                if not sequence:
                    sequence = Sequence()
                    sequence.name = "Party"
                    configuration.party_sequence = sequence

                sequence.sequence_type = ModelData.get_id('party', 'sequence_type_party')
                sequence.prefix = record.sequence_prefix
                sequence.suffix = record.sequence_suffix
                sequence.padding = record.sequence_padding
                sequence.number_next = record.sequence_number_next
                sequence.save()

            langs = Lang.search(["code", "=", record.language_code], limit=1)
            if langs:
                configuration.party_lang, = langs
            break

        Configuration.save(to_save)
        return [Configuration(1)]
