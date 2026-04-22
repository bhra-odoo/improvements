from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    mx_companies = env['res.company'].search([('chart_template', '=', 'mx')], order="parent_path")
    if not mx_companies:
        return

    ChartTemplate = env['account.chart.template']
    Account = env['account.account']
    IrModelData = env['ir.model.data']

    # 1. Run try_loading first so new template records (e.g. asset_80_month_linear) are created
    for company in mx_companies:
        ChartTemplate.try_loading('mx', company, force_create=False)

    acc_dep_xmlids = [
        'cuenta171_02_01', 'cuenta171_03_01', 'cuenta171_04_01', 'cuenta171_05_01',
        'cuenta171_16_01', 'cuenta171_17_01', 'cuenta171_18_01',
        'cuenta183_01_01', 'cuenta183_07_01',
    ]
    exp_dep_xmlids = [
        'cuenta613_02_01', 'cuenta613_03_01', 'cuenta613_04_01', 'cuenta613_05_01',
        'cuenta613_16_01', 'cuenta613_17_01', 'cuenta613_18_01',
        'cuenta614_01_01', 'cuenta614_07_01',
    ]
    asset_mappings = [
        ('cuenta153_01_01', 'cuenta171_02_01', 'cuenta613_02_01'),  # Machinery & equipment
        ('cuenta154_01_01', 'cuenta171_03_01', 'cuenta613_03_01'),  # Vehicles
        ('cuenta155_01_01', 'cuenta171_04_01', 'cuenta613_04_01'),  # Furniture & Office Equipment
        ('cuenta156_01_01', 'cuenta171_05_01', 'cuenta613_05_01'),  # Technology
        ('cuenta168_01_01', 'cuenta171_16_01', 'cuenta613_16_01'),  # Renewable Energy
        ('cuenta169_01_01', 'cuenta171_18_01', 'cuenta613_18_01'),  # Other Machines & Equipment
        ('cuenta170_01_01', 'cuenta171_17_01', 'cuenta613_17_01'),  # Upgrades and Retrofits
        ('cuenta179_01_01', 'cuenta183_07_01', 'cuenta614_07_01'),  # Brands and Patents
        ('cuenta173_01', 'cuenta183_01_01', 'cuenta614_01_01'),  # Deferred Expenses
    ]

    all_base_xmlids = set(
        acc_dep_xmlids + exp_dep_xmlids +
        [m[0] for m in asset_mappings] +
        [m[1] for m in asset_mappings] +
        [m[2] for m in asset_mappings] +
        ['asset_80_month_linear']
    )

    # 2. Fetch all needed ir.model.data records in one query
    target_names = [f"{company.id}_{xmlid}" for company in mx_companies for xmlid in all_base_xmlids]
    imds = IrModelData.search_read([
        ('module', 'in', ['account', 'l10n_mx']),
        ('name', 'in', target_names)
    ], ['name', 'res_id'])
    
    xmlid_map = {imd['name']: imd['res_id'] for imd in imds}

    acc_ids = []
    exp_ids = []

    def get_ids(company, xmlids):
        return [
            xmlid_map[name]
            for x in xmlids
            if (name := f"{company.id}_{x}") in xmlid_map
        ]

    for company in mx_companies:
        acc_ids.extend(get_ids(company, acc_dep_xmlids))
        exp_ids.extend(get_ids(company, exp_dep_xmlids))
    Account.browse(acc_ids).write({'account_type': 'asset_non_current'})
    Account.browse(exp_ids).write({'account_type': 'expense_depreciation'})

    # --- Asset mappings ---
    for company in companies:
        prefix = f"{company.id}_"
        asset_model_id = xmlid_map.get(prefix + 'asset_80_month_linear')

        for asset_xmlid, dep_xmlid, exp_xmlid in asset_mappings:
            asset_id = xmlid_map.get(prefix + asset_xmlid)
            if not asset_id:
                continue

            Account.browse(asset_id).write({
                'depreciation_model_id': asset_model_id,
                'asset_depreciation_account_id': xmlid_map.get(prefix + dep_xmlid),
                'asset_expense_account_id': xmlid_map.get(prefix + exp_xmlid),
            })
