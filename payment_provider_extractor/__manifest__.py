{
    "name": "payment_provider_extractor",
    "summary": "Extract payment settlements/transactions from different "
    "payment providers",
    "author": "Odoo Community Association (OCA)," "Hobbii",
    "website": "https://github.com/OCA/account-reconcile",
    "category": "Uncategorized",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "depends": ["base", "account"],
    "data": [
        "security/payment_provider_security.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/payment_provider_view.xml",
        "views/account_bank_statement_view.xml",
    ],
}
