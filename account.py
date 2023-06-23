from datetime import datetime
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.transaction import Transaction
from trytond.tools import grouped_slice


class ImporterAccountMove(ModelView):
    'Importer AccountMove'
    __name__ = 'importer.account.move'

    number = fields.Char('Move Number')
    journal_code = fields.Char('Journal Code')
    effective_date = fields.Date('Effecive Date')
    account_code = fields.Char('Account Code')
    account_name = fields.Char('Account Name')
    party_code = fields.Char('Party Code')
    party_name = fields.Char('Party Name')
    debit = fields.Float('Debit')
    credit = fields.Float('Credit')
    description = fields.Char('Description')


class ImporterChart(ModelView):
    'Importer Chart'
    __name__ = 'importer.account.chart'
    company_name = fields.Char('Company Name')
    chart_name = fields.Char('Chart Name')
    digits = fields.Integer('Digits')
    receivable_code = fields.Char('Receivable Code')
    payable_code = fields.Char('Payable Code')


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
        })
        return methods

    @classmethod
    def import_account_move_header(cls, record):
        return (record.number, record.effective_date)

    @classmethod
    def get_party_dict(cls):
        Party = Pool().get('party.party')
        with Transaction().set_context(active_test=False):
            return dict((x.code, x) for x in Party.search([]))

    def import_account_move(cls, records):
        return cls._import_account_move(records)

    def import_account_move_party(cls, records):
        return cls._import_account_move(records, create_party=True)

    def import_account_move_account(cls, records):
        return cls._import_account_move(records, create_account=True)

    def import_account_move_account_party(cls, records):
        return cls._import_account_move(records, create_party=True,
            create_account=True)

    @classmethod
    def get_dict_accounts(cls):
        pool = Pool()
        Account = pool.get('account.account')
        company = Transaction().context.get('company')
        accounts = dict((x.code, x) for x in Account.search([
            ('company', '=', company)
        ]))
        return accounts

    @classmethod
    def get_account_code(cls, account_code):
        return account_code

    @classmethod
    def get_party_code(cls, party_code):
        return party_code

    def _import_account_move(cls, records, create_party=False,
            create_account=False):
        pool = Pool()
        Account = pool.get('account.account')
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        Party = pool.get('party.party')
        PartyIdentifier = pool.get('party.identifier')
        AccountType = pool.get('account.account.type')
        Currency = pool.get('currency.currency')

        def _create_party(code, name):
            party = Party(name=name, code=code)
            party.identifiers = [PartyIdentifier(code=code, type=None)]
            return party

        accounts = cls.get_dict_accounts()
        clients = cls.get_party_dict()
        journals = dict((x.code, x) for x in Journal.search([]))

        periods = {}

        chart = {}
        company = Transaction().context.get('company')
        if create_account:
            chart = cls.get_chart_tree(company)
            account_type, = AccountType.search([('company', '=', company)],
                limit=1)

        moves = set((x.post_number, x.date)
               for x in Move.search([
                        ('company', '=', company),
                        ('period.state', '=', 'open'),
                        ]))
        moves_to_save = []
        previous_header = None
        accounts_to_save = []
        party_to_save = []
        for record in records:
            mdate = record.effective_date
            period = periods.get(mdate)
            if not period:
                period_id = Period.find(company, date=mdate, test_state=True)
                period = Period(period_id)
                periods[mdate] = period
            if isinstance(mdate, str):
                mdate = datetime.strptime(mdate, '%Y-%m-%d %H:%M:%s').date()
            elif isinstance(mdate, datetime):
                mdate = mdate.date()
            if (record.number, mdate) in moves:
                continue
            if record.account_code is None:
                print("Not account code:", record.account_code, record.number,
                      record.description, record.credit, record.debit)
                continue
            header = cls.import_account_move_header(record)
            acc_code = cls.get_account_code(record.account_code)
            account = accounts.get(acc_code, None)
            if not account:
                if create_account:
                    account = cls.create_account(acc_code,
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
                        if chart.get(cls.get_code(acc_code)):
                            account.parent = chart.get(cls.get_code(acc_code))
                if not account or account is None:
                    raise UserError(gettext('importer.account_not_found',
                        account=record.account_code))
                account.company = company
                accounts_to_save.append(account)
                accounts[account.code] = account

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
                move.journal = journals.get(record.journal_code)
                move.lines = []
                moves_to_save.append(move)

            party_code = cls.get_party_code(record.party_code)
            party = clients.get(party_code)
            if account.party_required and not party:
                if not create_party:
                    raise UserError(gettext(
                        'importer.party_required_for_account',
                        account=record.account_code, move=record.number))
                party = _create_party(party_code, record.party_name)
                clients[party.code] = party
                party_to_save.append(party)

            line = Line()
            line.account = account
            line.description = record.description

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

            line.debit = Decimal("%.2f" % (debit or 0))
            line.credit = Decimal("%.2f" % (credit or 0))
            if account.party_required:
                line.party = party
            if hasattr(account, 'second_currency') and account.second_currency:
                line.second_currency = account.second_currency
                line.amount_second_currency = Currency.compute(
                    account.currency, line.debit - line.credit,
                    account.second_currency)

            move.lines += (line, )

        if party_to_save:
            Party.save(party_to_save)
        if accounts_to_save:
            Account.save(accounts_to_save)

        for to_save in grouped_slice(moves_to_save):
            Move.save(list(to_save))
        return moves_to_save

    def create_account(self, code, name, chart):
        Configurator = Pool().get('account.configuration')
        config = Configurator(1)

        code = self.get_code(code)
        existing = chart.get(code)
        if existing:
            return
        digits = config.default_account_code_digits or 8
        similar_account = self.get_similar_account(code, chart, digits)
        if similar_account:
            account = self.similar_account(similar_account, {'code': code,
                'name': name})
        else:
            return
        account.code = code
        account.name = name
        chart[code] = account
        return account

    def get_similar_account(self, code, chart, digits=8):
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

    def similar_account(self, sim_account, vals):
        Account = Pool().get('account.account')
        account = Account()

        ignore_fields = ['id', 'code', 'name', 'childs', 'deferrals', 'taxes',
            'create_date', 'create_uid', 'write_date', 'write_uid', 'template',
            'parent', 'company', 'general_ledger_balance', 'balance', 'credit',
            'debit', 'right', 'left']

        for field in Account._fields:
            if field in ignore_fields:
                continue
            value = getattr(sim_account, field)
            setattr(account, field, value)

        if (sim_account.code and sim_account.parent
                and len(vals.get('code', '')) == len(sim_account.code)):
            account.parent = sim_account.parent
        else:
            account.parent = sim_account

        for k, v in vals.items():
            setattr(account, k, v)

        return account

    def get_account_party_codes(self):
        Account = Pool().get('account.account')
        accounts = Account.search([('party_required', '=', True)])
        return [x.code[0:4] for x in accounts]

    def get_code(self, code, digits=8):
        if len(code) > 4:
            if code[:4] in self.get_account_party_codes():
                return code[0:4].ljust(len(code), '0')
        return code

    def get_chart_tree(self, company):
        Account = Pool().get('account.account')
        accounts = Account.search([('company', '=', company)])
        return dict((str(a.code), a) for a in accounts)

    def import_account_create_chart(cls, records):
        "Create chart of accounts"
        pool = Pool()
        Account = pool.get('account.account')
        AccountTemplate = pool.get('account.account.template')
        Company = pool.get('company.company')
        CreateChart = pool.get('account.create_chart', type='wizard')

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

            session_id, _, _ = CreateChart.create()
            create_chart = CreateChart(session_id)
            create_chart.account.account_template = chart
            create_chart.account.company = company
            if record.digits:
                create_chart.account.account_code_digits = record.digits
            create_chart.transition_create_account()
            create_chart.properties.company = company
            create_chart.properties.account_receivable = None
            domain = [('type.receivable', '=', True)]
            if record.receivable_code:
                domain.append(('code', '=', record.receivable_code))

            accounts = Account.search(domain, limit=1)
            if accounts:
                create_chart.properties.account_receivable, = accounts
            create_chart.properties.account_payable = None
            domain = [('type.payable', '=', True)]
            if record.payable_code:
                domain.append(('code', '=', record.payable_code))
            accounts = Account.search(domain, limit=1)
            if accounts:
                create_chart.properties.account_payable, = accounts
            create_chart.transition_create_properties()

        return Account.search([('template', '=', chart)])

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

            if record.post_move_sequence_name:
                fiscalyear.post_move_sequence = move_sequences.get(
                    record.post_move_sequence_name)
            else:
                invoice_sequence = SequenceStrict()
                invoice_sequence.name = 'x'
                fiscalyear.post_move_sequence = None
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
        return invoice_sequences, move_sequences
