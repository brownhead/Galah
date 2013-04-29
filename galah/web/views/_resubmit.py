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

## The Actual View ##
from galah.web import app
from galah.web.auth import account_type_required
from bson.objectid import ObjectId
from bson.errors import InvalidId
from flask import abort, request, flash, redirect, url_for
from galah.db.models import Submission, Assignment, TestResult
from galah.shepherd.api import send_test_request
from galah.web.util import is_url_on_site, GalahWebAdapter
import datetime
import logging

# Load Galah's configuration
from galah.base.config import load_config
config = load_config("shepherd")

logger = \
    GalahWebAdapter(logging.getLogger("galah.web.views.upload_submissions"))

@app.route("/assignments/<assignment_id>/resubmit/<submission_id>")
@account_type_required(("student", "teacher", "teaching_assistant"))
def resubmit_submission(assignment_id, submission_id):
    # Figure out which assignment the submission belongs to.
    try:
        assignment_id = ObjectId(assignment_id)
        assignment = Assignment.objects.get(id = assignment_id)
    except (InvalidId, Assignment.DoesNotExist) as e:
        logger.info("Could not retrieve assignment: %s", str(e))

        abort(404)

    # Figure out where we should redirect the user to once we're done.
    redirect_to = request.args.get("next") or request.referrer

    if not is_url_on_site(app, redirect_to):
        # Default going back to the assignment screen
        redirect_to = url_for(
            "view_assignment",
            assignment_id = assignment_id
        )

    # Recheck if the assignment's cutoff date has passed.
    if assignment.due_cutoff and \
            assignment.due_cutoff < datetime.datetime.today():
        logger.info("Submission rejected, cutoff date has already passed.")

        return craft_response(
            error = "The cutoff date has already passed, your submission was "
                    "not accepted."
        )

    try:
        submission_id = ObjectId(submission_id)
        submission = Submission.objects.get(id = submission_id)
    except (InvalidId, Submission.DoesNotExist) as e:
        logger.info("Could not retrieve submission: %s", str(e))

        abort(404)

    # Recheck that this assignment has a test harness before signaling shepherd.
    if (assignment.test_harness):
        submission.test_request_timestamp = datetime.datetime.now()
        send_test_request(config["PUBLIC_SOCKET"], submission.id)
        logger.info("Resending test request to shepherd for %s" \
                        % str(submission.id))

        # If the test result failed, remove it from submissions and database
        if submission.test_results:
            result = TestResult.objects.get(id = submission.test_results)
            if result.failed:
                result.delete()
                submission.test_results = None

        # Save new reqeust timestamp in submission.
        submission.save()

        flash("Successfully resubmitted files.", category = "message")

    return redirect(redirect_to)
