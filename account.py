from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from types import SimpleNamespace
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.transaction import Transaction
from .tools import ImporterModel, Cache, Setup


class ImporterAccountMove(ImporterModel):
    'Importer Account Move'
    __name__ = 'importer.account.move'

    number = fields.Char('Move Number')
    journal_code = fields.Char('Journal Code')
    effective_date = fields.Date('Effecive Date')
    account_code = fields.Char('Account Code')
    account_name = fields.Char('Account Name')
    party_code = fields.Char('Party Code')
    party_name = fields.Char('Party Name')
    debit = fields.Numeric('Debit')
    credit = fields.Numeric('Credit')
    description = fields.Char('Description')
    maturity_date = fields.Date('Maturity Date')

    @classmethod
    def importer_start(cls):
        pool = Pool()
        Chart = pool.get('importer.account.chart')
        Company = pool.get('company.company')

        setup = Setup.get()
        cache = setup.cache
        company_id = Transaction().context.get('company')

        cache.analytic_accounts = Cache('analytic_account.account', 'name',
            required=False)
        cache.accounts = Cache('account.account', 'code', domain=[
                ('company', '=', company_id),
                ])
        cache.parties = Cache('party.party', 'code', context={'active_test': False})
        cache.journals = Cache('account.journal', 'code')
        cache.moves = Cache('account.move', lambda x: (x.post_number, x.date), domain=[
                ('company', '=', company_id),
                ('period.state', '=', 'open'),
                ('post_number', '!=', None),
                ])
        cache.account_party_codes = Chart.get_account_party_codes()
        cache.periods = {}
        cache.currency = Company(company_id).currency

    def importer_header(self, importing=True):
        return (self.number, self.effective_date)

    def get_party_code(self):
        return self.party_code

    def get_account_code(self):
        return self.account_code

    def get_new_party(self, code, name):
        pool = Pool()
        Party = pool.get('party.party')
        PartyIdentifier = pool.get('party.identifier')

        party = Party(name=name)
        if code:
            party.code = code
            party.identifiers = [PartyIdentifier(code=code, type=None)]
        return party

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        AccountType = pool.get('account.account.type')
        Currency = pool.get('currency.currency')
        Chart = pool.get('importer.account.chart')
        JournalPeriod = pool.get('account.journal.period')

        try:
            AnalyticLine = pool.get('analytic_account.line')
            AnalyticAccount = pool.get('analytic_account.account')
        except:
            pass

        # Account move line's check_journal_period_modify may lock the
        # the journal to create new periods. So we lock the journal period
        # at the very beginning to avoid that the lock is done much later
        # which would cause the transaction to restart.
        JournalPeriod.lock()

        setup = Setup.get()
        cache = setup.cache
        currency = cache.currency

        create_party = False
        create_account = False
        if setup.method == 'account_move_party':
            create_party = True
        elif setup.method == 'account_move_account':
            create_account = True
        elif setup.method == 'account_move_account_party':
            create_party = True
            create_account = True

        chart = {}
        company = Transaction().context.get('company')
        if create_account:
            chart = Chart.get_chart_tree(company)
            account_type, = AccountType.search([('company', '=', company)],
                limit=1)

        moves_to_save = []
        lines_to_save = []
        analytic_lines_to_save = []
        previous_header = None
        accounts_to_save = []
        parties_to_save = []
        analytic_accounts_to_save = []
        created_parties = {}
        for record in records:
            setup.current_record = record

            # Ensure the move list has to be created before create all the
            # related fields.
            debit = 0
            credit = 0
            if not record.debit:
                record.debit = 0
            if not record.credit:
                record.credit = 0
            if record.debit < 0:
                credit = abs(record.debit or 0)
            else:
                debit = record.debit or 0
            if record.credit < 0:
                debit += abs(record.credit or 0)
            else:
                credit += record.credit or 0

            # Control that only one debit or credit has value.
            # And none of them has, not create line.
            if debit and credit:
                balance = debit - credit
                if balance == 0:
                    continue
                elif balance < 0:
                    debit = 0
                    credit = abs(balance)
                else:
                    debit = balance
                    credit = 0
            elif not debit and not credit:
                continue

            mdate = record.effective_date
            period = cache.periods.get(mdate)
            if not period:
                period_id = Period.find(company, date=mdate, test_state=True)
                period = Period(period_id)
                cache.periods[mdate] = period
            if isinstance(mdate, str):
                mdate = datetime.strptime(mdate, '%Y-%m-%d %H:%M:%s').date()
            elif isinstance(mdate, datetime):
                mdate = mdate.date()
            if (record.number, mdate) in cache.moves:
                continue
            if record.account_code is None:
                continue
            acc_code = record.get_account_code()
            if not create_account:
                account = cache.accounts.get(acc_code)
            else:
                if acc_code in cache.accounts:
                    account = cache.accounts[acc_code]
                else:
                    account = Chart.create_account(acc_code,
                        record.account_name, chart)
                    if not account:
                        values = Account.default_get(
                            list(Account._fields.keys()), with_rec_name=False)
                        account = Account(**values)
                        account.code = acc_code
                        account.name = record.account_name
                        account.type = account_type
                        account.company = company
                        account.parent = None
                        if chart.get(Chart.get_code(acc_code)):
                            account.parent = chart.get(Chart.get_code(acc_code))
                    account.company = company
                    accounts_to_save.append((account, record))
                    cache.accounts.add(account)

            if not account:
                continue

            header = record.importer_header()
            if any(header) and header != previous_header:
                previous_header = header
                values = Move.default_get(list(Move._fields.keys()),
                    with_rec_name=False)

                date = record.effective_date
                move = Move(**values)
                move.date = date
                move.post_number = record.number
                move.number = record.number
                move.period = period
                move.journal = cache.journals.get(record.journal_code)
                move.lines = []
                moves_to_save.append((move, record))

            party_code = record.get_party_code()
            party = cache.parties.get(party_code)
            if account.party_required and not party:
                if not create_party:
                    raise UserError(gettext(
                        'importer.party_required_for_account',
                        account=record.account_code, move=record.number))
                party_name = record.party_name
                if party_name in created_parties:
                    party = created_parties[party_name]
                else:
                    party = record.get_new_party(party_code, party_name)
                    created_parties[party_name] = party
                    parties_to_save.append((party, record))

            line = Line()
            lines_to_save.append((line, record))
            line.move = move
            line.account = account
            line.description = record.description
            line.maturity_date = record.maturity_date
            line.debit = currency.round(debit)
            line.credit = currency.round(credit)
            if account.party_required:
                line.party = party
            if account.id is not None and account.second_currency:
                line.second_currency = account.second_currency
                line.amount_second_currency = Currency.compute(
                    account.currency, line.debit - line.credit,
                    account.second_currency)
            if 'analytic_account' in setup.fields and record.analytic_account:
                analytic_account = cache.analytic_accounts.get(
                    record.analytic_account)
                if not analytic_account:
                    analytic_account = AnalyticAccount()
                    root_account = AnalyticAccount.search([
                        ('type', '=', 'root'),
                        ('company', '=', company),
                        ], limit=1)
                    root_account = root_account[0] if root_account else None
                    analytic_account.name = record.analytic_account
                    analytic_account.company = company
                    analytic_account.type = 'normal'
                    analytic_account.root = root_account
                    analytic_account.parent = root_account
                    cache.analytic_accounts.add(analytic_account)
                    analytic_accounts_to_save.append((analytic_account, record))
                analytic_line = AnalyticLine()
                analytic_line.account = analytic_account
                analytic_line.date = record.effective_date
                analytic_line.debit = line.debit
                analytic_line.credit = line.credit
                analytic_line.move_line = line
                analytic_lines_to_save.append((analytic_line, record))

        setup.current_record = None
        cls.importer_save(parties_to_save)
        cls.importer_save(accounts_to_save)
        cls.importer_save(analytic_accounts_to_save)
        cls.importer_save(moves_to_save)
        cls.importer_save(lines_to_save)
        cls.importer_save(analytic_lines_to_save)
        return [x[0] for x in moves_to_save]


class ImporterAccountMoveDependsAnalytic(metaclass=PoolMeta):
    __name__ = 'importer.account.move'
    analytic_account = fields.Char('Analytic Account')


class ImporterChart(ModelView):
    'Importer Chart'
    __name__ = 'importer.account.chart'
    company_name = fields.Char('Company Name')
    chart_name = fields.Char('Chart Name')
    digits = fields.Integer('Digits')
    receivable_code = fields.Char('Receivable Code')
    payable_code = fields.Char('Payable Code')

    @classmethod
    def get_account_party_codes(cls):
        Account = Pool().get('account.account')

        company_id = Transaction().context.get('company')
        return [x.code[0:4] for x in Account.search([
                ('party_required', '=', True),
                ('company', '=', company_id),
                ])]

    @classmethod
    def get_code(cls, code, digits=8):
        setup = Setup.get()
        cache = setup.cache
        if len(code) > 4:
            if code[:4] in cache.account_party_codes:
                return code[0:4].ljust(len(code), '0')
        return code

    @classmethod
    def create_account(cls, code, name, chart):
        Configurator = Pool().get('account.configuration')
        config = Configurator(1)

        code = cls.get_code(code)
        existing = chart.get(code)
        if existing:
            return
        digits = config.default_account_code_digits or 8
        similar_account = cls.get_similar_account(code, chart, digits)
        if similar_account:
            account = cls.similar_account(similar_account, {'code': code,
                'name': name})
        else:
            return
        account.code = code
        account.name = name
        chart[code] = account
        return account

    @classmethod
    def get_similar_account(cls, code, chart, digits=8):
        account = None
        if len(code) < digits:
            for digits in (4, 3, 2, 1):
                code2 = code[:digits]
                account = chart.get(code2)
                if account:
                    break

        if len(code) == digits:
            # Ensure that we find a valid account
            for i in range(len(code)):
                sub_code = code[:-i].ljust(digits, '0')
                if sub_code in chart:
                    new_account = chart.get(sub_code)
                    if new_account.type is not None:
                        account = new_account
                        break

        if account:
            return account

    @classmethod
    def similar_account(cls, sim_account, vals):
        Account = Pool().get('account.account')

        account = Account()
        ignore_fields = ['id', 'code', 'name', 'childs', 'deferrals', 'taxes',
            'create_date', 'create_uid', 'write_date', 'write_uid', 'template',
            'parent', 'company', 'general_ledger_balance', 'balance', 'credit',
            'debit', 'right', 'left']

        for fname, field in Account._fields.items():
            if isinstance(field, fields.Function):
                continue
            if fname in ignore_fields:
                continue
            value = getattr(sim_account, fname)
            setattr(account, fname, value)

        if (sim_account.code and sim_account.parent
                and len(vals.get('code', '')) == len(sim_account.code)):
            account.parent = sim_account.parent
        else:
            account.parent = sim_account

        for k, v in vals.items():
            setattr(account, k, v)

        return account

    @classmethod
    def get_chart_tree(cls, company):
        Account = Pool().get('account.account')
        accounts = Account.search([('company', '=', company)])
        return dict((str(a.code), a) for a in accounts)


class ImporterFiscalYear(ModelView):
    'Importer Fiscal Year'
    __name__ = 'importer.account.fiscalyear'
    name = fields.Char('Name')
    company_name = fields.Char('Company Name')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    post_move_sequence_name = fields.Char('Post Move Sequence Name')
    in_invoice_sequence_name = fields.Char('In Invoice Sequence Name')
    out_invoice_sequence_name = fields.Char('Out Invoice Sequence Name')
    in_credit_note_sequence_name = fields.Char('In Credit Note Sequence Name')
    out_credit_note_sequence_name = fields.Char('Out Credit Note Sequence Name')


class ImporterAccountAsset(ModelView):
    'Importer Account Asset'
    __name__ = 'importer.account.asset'
    value = fields.Char('Value')
    product_code = fields.Char('Product Code')
    product_name = fields.Char('Product Name')
    depreciated_amount = fields.Char('Depreciated Amount')
    residual_value = fields.Char('Residual Value')
    current_value = fields.Char('Current Value')
    purchase_date = fields.Date('Purchase Date')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    comment = fields.Char('Comment')
    number = fields.Char('Number')


class ImporterAccountAssetAnalyticDepends(metaclass=PoolMeta):
    __name__ = 'importer.account.asset'
    analytic_account = fields.Char('Analytic Account')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
            'account_move': {
                'string': 'Account Move',
                'model': 'importer.account.move',
                'chunked': False,
                },
            'account_move_party': {
                'string': 'Account Move Create Missing Party',
                'model': 'importer.account.move',
                'chunked': False,
                },
            'account_move_account': {
                'string': 'Account Move Create Missing Account',
                'model': 'importer.account.move',
                'chunked': False,
                },
            'account_move_account_party': {
                'string': 'Account Move Create Missing Account and Party',
                'model': 'importer.account.move',
                'chunked': False,
                },
            'account_create_chart': {
                'string': 'Create Chart of Accounts',
                'model': 'importer.account.chart',
                'chunked': False,
                },
            'account_fiscalyear': {
                'string': 'Fiscal Year',
                'model': 'importer.account.fiscalyear',
                'chunked': False,
                },
            'account_asset': {
                'string': 'Asset',
                'model': 'importer.account.asset',
                'chunked': False,
                },
        })
        return methods

    @classmethod
    def import_account_asset(cls, records):
        pool = Pool()
        Asset = pool.get('account.asset')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        Company = pool.get('company.company')

        cache = SimpleNamespace()
        cache.templates = dict((x.code, x) for x in
                Product.search([
                ('code', '!=', None),
                ('code', '!=', ''),
                ]))
        try:
            AnalyticAccount = pool.get('analytic_account.account')
            AnalyticEntry = pool.get('analytic.account.entry')
            cache.analytic_accounts = dict((x.code, x) for x in
                AnalyticAccount.search([]))
        except:
            pass

        company = Company(Transaction().context.get('company'))
        currency = company.currency

        imported = []
        for record in records:
            found_product = []
            if record.product_code:
                found_product = Product.search(
                    [('code', '=', record.product_code )], limit=1)
            elif record.product_name:
                found_product = Product.search(
                    [('name', '=', record.product_name )], limit=1)
            if not found_product:
                raise UserError(gettext('importer.msg_asset_product_not_found',
                    product=record.product_code))
            product = found_product[0]
            asset = Asset()
            asset.number = record.number if record.number else None
            asset.product = product
            asset.value = currency.round(Decimal(record.value or 0))
            asset.comment = record.comment
            asset.purchase_date = record.purchase_date
            asset.start_date = record.start_date or record.purchase_date
            depreciated_amount = 0.0
            if record.depreciated_amount is not None:
                depreciated_amount = currency.round(Decimal(record.depreciated_amount))
            elif record.current_value is not None and asset.value is not None:
                depreciated_amount = currency.round(asset.value - Decimal(record.current_value))
                asset.start_date = Date.today()
            asset.depreciated_amount = depreciated_amount
            asset.residual_value = (currency.round(Decimal(record.residual_value))
                if record.residual_value is not None else 0.0)
            if record.end_date:
                asset.end_date = record.end_date
            elif product.depreciation_duration:
                asset.end_date = (asset.purchase_date + relativedelta(
                    days=-1, months=product.depreciation_duration))
            # Do not import if the end date is in the past
            if asset.end_date < Date.today():
                continue
            if hasattr(Asset, 'analytic_accounts') and record.analytic_account:
                account = cache.analytic_accounts.get(record.analytic_account)
                if account:
                    root = account.root
                    entry = AnalyticEntry()
                    entry.root = root
                    entry.account = account
                    asset.analytic_accounts = [entry]
            imported.append(asset)
        Asset.save(imported)
        return imported

    def import_account_create_chart(cls, records):
        "Create chart of accounts"
        pool = Pool()
        Account = pool.get('account.account')
        AccountTemplate = pool.get('account.account.template')
        Company = pool.get('company.company')
        CreateChart = pool.get('account.create_chart', type='wizard')

        chart_ids = []
        for record in records:
            record.company_name

            companies = Company.search([
                    ('party.name', '=', record.company_name),
                    ], limit=1)
            if not companies:
                raise UserError(gettext('importer.msg_company_not_found',
                        company=record.company_name))
            company, = companies

            charts = AccountTemplate.search([
                    ('name', '=', record.chart_name),
                    ])
            if not charts:
                raise UserError(gettext('importer.msg_chart_not_found',
                        chart=record.chart_name))
            chart, = charts
            chart_ids.append(chart.id)

            session_id, _, _ = CreateChart.create()
            create_chart = CreateChart(session_id)
            create_chart.account.account_template = chart
            create_chart.account.company = company
            if record.digits:
                create_chart.account.account_code_digits = record.digits
            create_chart.transition_create_account()
            create_chart.properties.company = company
            create_chart.properties.account_receivable = None
            domain = [('type.receivable', '=', True), ('party_required', '=', True)]
            if record.receivable_code:
                domain.append(('code', '=', record.receivable_code))

            accounts = Account.search(domain, limit=1)
            if accounts:
                create_chart.properties.account_receivable, = accounts
            create_chart.properties.account_payable = None
            domain = [('type.payable', '=', True), ('party_required', '=', True)]
            if record.payable_code:
                domain.append(('code', '=', record.payable_code))
            accounts = Account.search(domain, limit=1)
            if accounts:
                create_chart.properties.account_payable, = accounts
            create_chart.transition_create_properties()

        return Account.search([('template', 'in', chart_ids)])

    def import_account_fiscalyear(cls, records):
        pool = Pool()
        Company = pool.get('company.company')
        Sequence = pool.get('ir.sequence')
        SequenceStrict = pool.get('ir.sequence.strict')
        ModelData = pool.get('ir.model.data')
        FiscalYear = pool.get('account.fiscalyear')
        InvoiceSequence = pool.get('account.fiscalyear.invoice_sequence')

        type_invoice_id = ModelData.get_id('account_invoice',
            'sequence_type_account_invoice')
        type_accont_move_id = ModelData.get_id('account',
            'sequence_type_account_move')

        # Create a dictionary with the sequences of sequence_type = 'account.invoice'
        invoice_sequences = {x.name: x for x in
            SequenceStrict.search([('sequence_type', '=', type_invoice_id)])}
        move_sequences = {x.name: x for x in
            Sequence.search([('sequence_type', '=', type_accont_move_id)])}
        companies = {x.party.name: x for x in Company.search([])}
        fiscalyears = {x.name: x for x in FiscalYear.search([])}

        imported = []
        for record in records:
            fiscalyear = fiscalyears.get(record.name)
            if not fiscalyear:
                fiscalyear = FiscalYear()
                fiscalyear.name = record.name
                seq = InvoiceSequence()
                seq.company = companies.get(record.company_name)
                fiscalyear.invoice_sequences = [seq]
            else:
                seq = fiscalyear.invoice_sequences[0]
            fiscalyear.start_date = record.start_date
            fiscalyear.end_date = record.end_date
            fiscalyear.company = companies.get(record.company_name)

            fiscalyear.post_move_sequence = move_sequences.get(
                record.post_move_sequence_name)
            seq.out_invoice_sequence = invoice_sequences.get(
                record.out_invoice_sequence_name)
            seq.in_invoice_sequence = invoice_sequences.get(
                record.in_invoice_sequence_name)
            seq.out_credit_note_sequence = invoice_sequences.get(
                record.out_credit_note_sequence_name)
            seq.in_credit_note_sequence = invoice_sequences.get(
                record.in_credit_note_sequence_name)
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            imported.append(fiscalyear)
        return imported
