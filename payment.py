from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from .tools import ImporterModel, Cache, Setup
from collections import defaultdict
from trytond.exceptions import UserError
from trytond.i18n import gettext

class ImporterAccountPaymentGroup(ImporterModel):
    'Importer Account Payment Group'
    __name__ = 'importer.account.payment.group'
    payment_type = fields.Char('Payment Type')
    invoice_number = fields.Char('Invoice Number')
    vat = fields.Char('VAT Number')
    party_name = fields.Char('Account Name')
    amount = fields.Numeric('Amount')
    payment_date = fields.Date('Payment Date')
    journal = fields.Char('Journal')

    @classmethod
    def importer_start(cls):
        setup = Setup.get()
        cache = setup.cache
        transaction = Transaction()

        company_id = transaction.context.get('company')
        cache.parties = Cache('party.party', lambda x: (x.name.lower(),
                            (x.identifiers[0].code.lower() if
                             x.identifiers else None)))
        cache.payment_types = Cache('account.payment.type', 'code',
                                domain=[('company', '=', company_id),
                                        ('kind', '=', 'payable'),])
        cache.invoices = Cache('account.invoice', 'number',
                                domain=[('company', '=', company_id),])
        cache.journals = Cache('account.payment.journal',
                               lambda x: (x.name.lower(),
                                          x.payment_type.code.lower()),
                               domain=[('company', '=', company_id),])
        cache.sepa_mandates = Cache('account.payment.sepa.mandate',
                                    lambda x: (x.party.id, x.account_number.id),
                                    domain=[('company', '=', company_id),
                                            ('state', '=', ['validated'])])

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        Payment = pool.get('account.payment')
        Group = pool.get('account.payment.group')
        MoveLine = pool.get('account.move.line')
        Message = pool.get('account.payment.sepa.message')
        Mandate = pool.get('account.payment.sepa.mandate')
        CreatePaymentGroup = pool.get('account.move.line.create_payment_group',
                                      type='wizard')
        Date = pool.get('ir.date')
        today = Date.today()

        transaction = Transaction()
        setup = Setup.get()
        cache = setup.cache

        group_set = defaultdict(list)
        for record in records:
            group_set[(record.payment_type, record.payment_date,
                       record.journal)].append(record)

        new_groups = []
        line_amounts = {}
        for (payment_code, payment_date, journal_name), payments in group_set.items():
            move_lines = []
            for payment in payments:
                invoice = cache.invoices.get(payment.invoice_number)
                if not invoice or invoice.state != 'posted':
                    continue
                payment_type = cache.payment_types.get(payment_code)
                if not payment_type:
                    continue
                party = cache.parties.get((payment.party_name, payment.vat))
                if not party:
                    continue
                journal = cache.journals.get((journal_name, payment_code))
                if not journal:
                    continue
                bank_account = (party.receivable_bank_account or
                                (party.bank_accounts[0]
                                if party.bank_accounts else None))
                bank_number = (bank_account.numbers[0]
                        if bank_account and bank_account.numbers else None)
                if 'sepa' in setup.method:
                    if not bank_number:
                        raise UserError(gettext(
                            'importer.payment_sepa_no_bank_number',
                            party=payment.party_name))
                    mandate = cache.sepa_mandates.get((party.id, bank_number.id))
                    if mandate:
                        continue
                    mandate = Mandate()
                    mandate.party = party
                    mandate.account_number = bank_number
                    mandate.identification = (party.rec_name.split()[0] +
                                              '-' + bank_number.rec_name[-10:])
                    mandate.signature_date = today
                    mandate.save()
                    mandate.request([mandate])
                    mandate.validate_mandate([mandate])
                    cache.sepa_mandates[(party.id,
                                         bank_number.id)] = mandate
                for line in invoice.move.lines:
                    if (line.party and line.party == party and
                        line.payment_type == payment_type):
                        used_line = Payment.search([
                            ('line', '=', line.id),
                            ('state', '!=', 'failed')], limit=1)
                        if used_line:
                            continue
                        move_lines.append(line)
                        line_amounts[line.id] = payment.amount
            if not move_lines:
                continue
            MoveLine.save(move_lines)
            with transaction.set_context(active_id = None,
                    active_ids=[l.id for l in move_lines],
                    active_model='account.move.line'):
                session_id, _, _ = CreatePaymentGroup.create()
                create_group = CreatePaymentGroup(session_id)
                create_group.start.journal = journal
                create_group.start.planned_date = payment_date
                create_group.start.join = False
                action, data = create_group.do_create_(action=None)
                CreatePaymentGroup.delete(session_id)
                new_groups.extend(Group.browse(data['res_id']))
        for group in new_groups:
            for payment in group.payments:
                payment.amount = line_amounts[payment.line.id]
            Payment.save(group.payments)
            to_cancel_messages = []
            for message in group.sepa_messages:
                to_cancel_messages.append(message)
            Message.cancel(to_cancel_messages)
            group.sepa_generate_message([group])
        return new_groups


class ImporterAccountPaymentSEPAESDepends(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'account_payment_group': {
                'string': 'Payment Group',
                'model': 'importer.account.payment.group',
                'chunked': False,
            },
            'account_payment_group_sepa': {
                'string': 'Payment Group SEPA',
                'model': 'importer.account.payment.group',
                'chunked': False,
            }})
        return methods