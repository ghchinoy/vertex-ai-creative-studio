# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

# Dedicated logger for tracking the suppressed error
race_condition_logger = logging.getLogger("genmedia.race_condition_tracker")


class GenerationError(Exception):
    """Custom exception for video generation errors."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class AsyncVeoPollingFailedError(Exception):
    """Exception for failures during async Veo job polling."""



class UnknownHandlerIdFilter(logging.Filter):
    """A logging filter to suppress 'Unknown handler id' errors."""

    def filter(self, record):
        # Suppress the specific benign error message from Mesop
        if "Unknown handler id" in record.getMessage():
            # Log to a separate, non-disruptive logger for tracking purposes
            race_condition_logger.info(
                "Suppressed 'Unknown handler id' error",
                extra={"original_record": record.getMessage()},
            )
            return False  # Prevent the original logger from processing it
        return True
