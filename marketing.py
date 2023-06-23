from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool


class ImporterMarketingEmail(ModelView):
    'Importer Marketing Email'
    __name__ = 'importer.marketing.email'

    mailing_list = fields.Char('Mailing List', required=True)
    email = fields.Char('Email', required=True)


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
        existing = set([(x.email, x.list_.name) for x in Email.search([])])

        to_save = []
        for record in records:
            if not record.email:
                continue
            if not record.mailing_list:
                continue
            if record.mailing_list not in lists:
                continue
            if (record.email, record.mailing_list) in existing:
                continue
            email = Email()
            email.email = record.email
            email.list_ = lists[record.mailing_list]
            to_save.append(email)

        Email.save(to_save)
        return to_save
