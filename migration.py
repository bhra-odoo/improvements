from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    mx_companies = env['res.company'].search([('chart_template', '=', 'mx')], order="parent_path")
    if not mx_companies:
        return

    # 1. Run try_loading first so new template records (e.g. asset_80_month_linear) are created
    for company in mx_companies:
        env['account.chart.template'].try_loading('mx', company, force_create=False)

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
    target_names = [f"{company.id}_{x}" for company in mx_companies for x in all_base_xmlids]
    imds = env['ir.model.data'].search_read([
        ('module', 'in', ['account', 'l10n_mx']),
        ('name', 'in', target_names)
    ], ['name', 'res_id'])
    
    xmlid_to_res_id = {imd['name']: imd['res_id'] for imd in imds}

    Account = env['account.account']
    for company in mx_companies:
        def get_ids(xmlids):
            return [
                xmlid_to_res_id[name]
                for x in xmlids
                if (name := f"{company.id}_{x}") in xmlid_to_res_id
            ]

        acc_ids = get_ids(acc_dep_xmlids)
        if acc_ids:
            Account.browse(acc_ids).write({'account_type': 'asset_non_current'})

        exp_ids = get_ids(exp_dep_xmlids)
        if exp_ids:
            Account.browse(exp_ids).write({'account_type': 'expense_depreciation'})

        asset_model_id = xmlid_to_res_id.get(f"{company.id}_asset_80_month_linear")
        
        for asset_xmlid, dep_xmlid, exp_xmlid in asset_mappings:
            asset_res_id = xmlid_to_res_id.get(f"{company.id}_{asset_xmlid}")
            if not asset_res_id:
                continue

            vals = {}
            if asset_model_id:
                vals['depreciation_model_id'] = asset_model_id

            dep_res_id = xmlid_to_res_id.get(f"{company.id}_{dep_xmlid}")
            if dep_res_id:
                vals['asset_depreciation_account_id'] = dep_res_id

            exp_res_id = xmlid_to_res_id.get(f"{company.id}_{exp_xmlid}")
            if exp_res_id:
                vals['asset_expense_account_id'] = exp_res_id

            if vals:
                Account.browse(asset_res_id).write(vals)
