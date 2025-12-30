from datetime import datetime

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Example Project"
copyright = "2023, Anonymous"
author = "Anonymous"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["myst_parser", "sphinx_rtd_theme"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_last_updated_fmt = "%b %d, %Y"


def setup(app):
    app.connect("html-page-context", override_last_updated)


def override_last_updated(app, pagename, templatename, context, doctree):
    # Check if the page has metadata
    if "meta" in context and context["meta"]:
        # Look for your custom 'last_updated' key in the metadata
        custom_date = context["meta"].get("last_updated")

        if custom_date:
            try:
                # Parse the date string from frontmatter
                date_obj = datetime.strptime(custom_date, "%Y-%m-%d")

                # Format it using the global Sphinx config format
                # and OVERRIDE the context variable
                fmt = app.config.html_last_updated_fmt or "%b %d, %Y"
                context["last_updated"] = date_obj.strftime(fmt)

            except ValueError:
                # Fallback or warning if the date format in frontmatter is wrong
                print(f"Warning: Invalid date format in {pagename}: {custom_date}")
