from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from decimal import Decimal
import logging

class ImporterAccountMove(ModelView):
    'Importer AccountMove'
    __name__ = 'importer.account.move'

    number = fields.Char('Move Number')
    journal_code = fields.Char('Journal Code')
    effective_date = fields.Date('Effecive Date')
    account_code = fields.Char('Account Code')
    party_code = fields.Char('Party Code')
    debit = fields.Float('Debit')
    credit = fields.Float('Credit')
    description = fields.Char('Description')

logger = logging.getLogger(__name__)

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
        })
        return methods

    @classmethod
    def import_account_move_header(cls, record):
        return record.number

    @classmethod
    def get_party_dict(cls):
        Party = Pool().get('party.party')
        return dict((x.code, x) for x in Party.search([]))

    def import_account_move(cls, records):
        pool = Pool()
        Account = pool.get('account.account')
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        accounts = dict((x.code, x) for x in Account.search([]))
        clients = cls.get_party_dict()
        journals = dict((x.code, x) for x in Journal.search([]))

        moves_to_save = []
        previous_header = None
        for record in records:
            header = cls.import_account_move_header(record)
            account = accounts.get(record.account_code, None)
            if not account:
                logger.info("Account: %s not found " % record.account_code)
                continue
            if header and header != previous_header:
                previous_header = header
                values = Move.default_get(list(Move._fields.keys()),
                    with_rec_name=False)

                period, = Period.search([
                    ('start_date', '<=', record.effective_date),
                    ('end_date', '>=', record.effective_date)])
                move = Move(**values)
                move.date = record.effective_date
                move.period = period
                move.journal = journals.get(record.journal_code)
                move.lines = []
                moves_to_save.append(move)
                move.number = record.number

            party = clients.get(record.party_code)
            line = Line()
            line.account = account
            line.description = record.description
            line.debit = Decimal("%.2f" % (record.debit or 0))
            line.credit = Decimal("%.2f" % (record.credit or 0))
            line.party = party
            if line.account.party_required and not line.party:
                logger.info("Account: %s configured as party required, but"
                    "party not passed on line on record %s-%s" % (
                        line.account.code, record.account_code,
                        record.party_code))

            move.lines += (line, )
        Move.save(moves_to_save)
        return moves_to_save
