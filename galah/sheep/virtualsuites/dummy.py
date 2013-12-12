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

import time

# Performs one time setup for the entire module
def setup(logger):
    logger.debug("setup called. Doing nothing.")

class Producer:
	def __init__(self, logger):
		self.logger = logger

	def produce_vm(self):
		self.logger.debug("produce_vm called. Doing nothing.")
		time.sleep(10)
		return 0

class Consumer:
    def __init__(self, logger, thread):
        self.logger = logger
        self.thread = thread

    def prepare_machine(self):
        self.logger.debug("prepare machine called. Doing nothing.")
        time.sleep(10)
        return 0

    def run_test(self, container_id, test_request):
        self.logger.debug("run_test called. Doing nothing.")
        time.sleep(20)
        return {"_id": test_request["submission"]["id"], "tests": [{"message": "Could not find `main.cpp`.", "score": 0, "max_score": 1, "name": "File Name Correct"}, {"parts": [["Found Hello", 0, 0.5], ["Found World", 0, 0.5]], "score": 0, "max_score": 1, "name": "Found Hello World"}], "score": 0, "max_score": 2}
