# Copyright 2012-2013 Galah Group LLC
# Copyright 2012-2013 Other contributers as noted in the CONTRIBUTERS file
#
# This file is part of Galah.
#
# You can redistribute Galah and/or modify it under the terms of
# the Galah Group General Public License as published by
# Galah Group LLC, either version 1 of the License, or
# (at your option) any later version.
#
# Galah is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Galah Group General Public License for more details.
#
# You should have received a copy of the Galah Group General Public License
# along with Galah.  If not, see <http://www.galahgroup.com/licenses>.

# The actual view
from galah.web import app
from flask import render_template, url_for
from werkzeug.exceptions import InternalServerError, NotFound

from galah.web.util import GalahWebAdapter
import logging
logger = GalahWebAdapter(logging.getLogger("galah.web.views.error"))

from galah.base.config import load_config
config = load_config("web")

@app.errorhandler(404)
def notfound(e):
    logger.info("User accessed unavailable page.")

    return render_template("notfound.html"), 404

@app.errorhandler(500)
def error(e):
    # Log the error if it's not a 404 or purposeful abort(500).
    if type(e) is not InternalServerError and type(e) is not NotFound:
        logger.exception("An error occurred while rendering a view.")

    return render_template(
        "error.html",
        report_to = config["REPORT_ERRORS_TO"]
    ), 500

@app.errorhandler(413)
def toobig(e):
	logger.info("User tried to upload a file that was too large.")

	return render_template("toobig.html"), 413
