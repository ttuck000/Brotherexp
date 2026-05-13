from app import app
import importlib, os

# show registered routes (helpful to confirm blueprints loaded)
print("Registered routes:")
for r in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
    print(r.rule, "->", r.endpoint)

# fallback registration for legacy endpoints (import at runtime to avoid circular imports)
try:
    mod = importlib.import_module('app.purchase.routes')
    # vendor / warehouse aliases if present
    fn_vendor = getattr(mod, 'get_vendor_options', None) or getattr(mod, 'purchase_vendor_options', None)
    fn_wh = getattr(mod, 'get_warehouse_options', None) or getattr(mod, 'purchase_warehouse_options', None)

    if fn_vendor:
        app.add_url_rule('/purchase/api/vendor/options', view_func=fn_vendor)
        app.add_url_rule('/api/purchase/vendor/options', view_func=fn_vendor)
        print('Fallback registered: vendor options')

    if fn_wh:
        app.add_url_rule('/purchase/api/warehouse/options', view_func=fn_wh)
        app.add_url_rule('/api/purchase/warehouse/options', view_func=fn_wh)
        print('Fallback registered: warehouse options')

    # other fallbacks (list-detail, payments, summary_nopay)
    fn_list_detail = getattr(mod, 'get_purchase_list_detail', None)
    if fn_list_detail:
        app.add_url_rule('/purchase/api/list-detail', endpoint='purchase_list_detail_fallback', view_func=fn_list_detail, methods=['GET','POST'])
        app.add_url_rule('/api/purchase/list-detail', endpoint='purchase_list_detail_fallback2', view_func=fn_list_detail, methods=['GET','POST'])
        print('Fallback registered: purchase list-detail')

    fn_payments = getattr(mod, 'get_purchase_payments', None)
    if fn_payments:
        app.add_url_rule('/purchase/api/purchase_payments', endpoint='purchase_payments_fallback', view_func=fn_payments, methods=['GET','OPTIONS','HEAD'])
        app.add_url_rule('/api/purchase/purchase_payments', endpoint='purchase_payments_fallback2', view_func=fn_payments, methods=['GET','OPTIONS','HEAD'])
        print('Fallback registered: purchase_payments')

    fn_nopay = getattr(mod, 'purchase_payment_summary_nopay', None)
    if fn_nopay:
        app.add_url_rule('/purchase/payment/summary_nopay', endpoint='purchase_payment_summary_nopay_fallback', view_func=fn_nopay, methods=['GET','POST','OPTIONS','HEAD'])
        print('Fallback registered: /purchase/payment/summary_nopay')

except Exception as e:
    print('Fallback registration skipped or failed:', e)

# debug info about jinja/template resolution (optional)
print("app.import_name:", app.import_name)
print("app.root_path:", app.root_path)
print("app.template_folder:", app.template_folder)
print("template index exists at:", os.path.exists(os.path.join(app.template_folder, 'index.html')))

# run via app_entry.py in normal use; run.py can be used for dev run as well.
if __name__ == '__main__':
    # use app_entry.py / waitress in production; keep simple dev server here
    app.run(debug=True, host='127.0.0.1', port=7777)