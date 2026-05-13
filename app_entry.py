from app import app
import webbrowser
import os
import sys
from jinja2 import ChoiceLoader, FileSystemLoader
from flask import redirect, url_for, render_template

# Optional: open browser once when running locally
url = "http://127.0.0.1:7777"
if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    try:
        webbrowser.open_new(url)
    except Exception:
        pass

# --- ensure Flask uses the correct templates folder (supports PyInstaller onefile) ---
if getattr(sys, "frozen", False):
    base_for_resources = getattr(sys, "_MEIPASS")
else:
    base_for_resources = os.path.dirname(os.path.abspath(__file__))

templates_path = os.path.join(base_for_resources, "templates")
app.template_folder = templates_path

fs_loader = FileSystemLoader(templates_path)
existing = getattr(app, "jinja_loader", None)
if existing is None:
    app.jinja_loader = fs_loader
else:
    if isinstance(existing, ChoiceLoader):
        app.jinja_loader = ChoiceLoader([fs_loader] + existing.loaders)
    else:
        app.jinja_loader = ChoiceLoader([fs_loader, existing])

# debug prints
print("TEMPLATES PATH:", templates_path)
print("index.html exists:", os.path.exists(os.path.join(templates_path, "index.html")))
print("app.template_folder:", app.template_folder)

@app.before_request
def debug_jinja_loader():
    try:
        loader = app.jinja_loader
        print("DEBUG JINJA loader type:", type(loader))

        searchpaths = []
        if hasattr(loader, "searchpath"):
            searchpaths.extend(loader.searchpath or [])

        if isinstance(loader, ChoiceLoader):
            for sub in loader.loaders:
                if hasattr(sub, "searchpath"):
                    searchpaths.extend(sub.searchpath or [])
                else:
                    searchpaths.append(f"<{type(sub).__name__}>")

        print("DEBUG JINJA resolved searchpaths:", searchpaths)
        exists = any(
            os.path.exists(os.path.join(p, "index.html"))
            for p in searchpaths
            if isinstance(p, str) and os.path.isdir(p)
        )
        print("DEBUG index exists in searchpath:", exists)
    except Exception as e:
        print("DEBUG jinja check error:", e)

# debug: show all registered routes
print("Registered routes:")
for rule in app.url_map.iter_rules():
    print(rule, "->", rule.endpoint)

@app.route('/purchase/in')
def _purchase_in_redirect():
    return render_template('purchase/purchase_in.html')

@app.route('/purchase/in2')
def _purchase_in2_redirect():
    return render_template('purchase/purchase_in2.html')

if __name__ == "__main__":
    try:
        from waitress import serve
    except Exception:
        serve = None

    if serve:
        serve(app, host='0.0.0.0', port=7777)
    else:
        app.run(debug=True, use_reloader=False, host='0.0.0.0', port=7777)