from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


class ImporterMarketingEmail(ModelView):
    'Importer Marketing Email'
    __name__ = 'importer.marketing.email'

    mailing_list = fields.Char('Mailing List', required=True)
    email = fields.Char('Email', required=True)
    active = fields.Boolean('Active')


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'marketing_email': {
                    'string': 'Marketing Email',
                    'model': 'importer.marketing.email',
                    'chunked': True,
                    },
                })
        return methods

    @classmethod
    def import_marketing_email(cls, records):
        pool = Pool()
        List = pool.get('marketing.email.list')
        Email = pool.get('marketing.email')

        lists = {x.name: x for x in List.search([])}
        with Transaction().set_context(active_test=False):
            existing = {(x.email.strip().lower(), x.list_.name.strip()): x
                for x in Email.search([])}

        to_save = []
        for record in records:
            if not record.email:
                continue
            address = record.email.strip().lower()
            if not address:
                continue
            if not record.mailing_list:
                continue
            if record.mailing_list not in lists:
                continue
            if (address, record.mailing_list) in existing:
                email = existing[(address, record.mailing_list)]
                if not email.id:
                    # If e-mail is found twice in the data set we ignore the
                    # second one because trying to save the same new object
                    # twice will raise an error.
                    continue
            else:
                email = Email()
                email.email = address
                email.list_ = lists[record.mailing_list]
                existing[(address, record.mailing_list)] = email
            if record.active is not None:
                email.active = record.active
            to_save.append(email)

        Email.save(to_save)
        return to_save
