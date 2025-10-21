    @classmethod
    def importer_start(cls):
        setup = Setup.get()
        cache = setup.cache

        cache.companies = Cache('company.company',
            key=lambda x: x.party.name.lower())
        cache.journals = Cache('account.journal', 'code')

    def importer_context(self):
        res = super().importer_context()
        setup = Setup.get()
        if 'company' in setup.fields and self.company_name:
            company = setup.cache.companies.get(self.company_name)
            if company:
                res['company'] = company.id
        return res
