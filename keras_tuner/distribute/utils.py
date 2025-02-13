# Copyright 2019 The KerasTuner Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Distribution utilities."""

import os

import tensorflow as tf


def has_chief_oracle():
    """Checks for distributed tuning with a chief Oracle.

    `CloudOracle` manages its own distribution so should not set
    "KERASTUNER_ORACLE_IP".

    Returns:
        Boolean, whether distributed tuning with a chief Oracle should be run.
    """
    if "KERASTUNER_ORACLE_IP" in os.environ:
        if "KERASTUNER_ORACLE_PORT" not in os.environ:
            raise RuntimeError(
                'Environment variable "KERASTUNER_ORACLE_IP" was set, '
                'but "KERASTUNER_ORACLE_PORT" was not. Please specify '
                "a port."
            )
        if "KERASTUNER_TUNER_ID" not in os.environ:
            raise RuntimeError(
                'Environment variable "KERASTUNER_ORACLE_IP" was set, '
                'but "KERASTUNER_TUNER_ID" was not. Please specify '
                "an ID for each tuner."
            )
        return True
    return False


def is_chief_oracle():
    if has_chief_oracle():
        return "chief" in os.environ["KERASTUNER_TUNER_ID"]
    return False


# Below is forked from Keras:
# https://github.com/keras-team/keras/blob/master/keras/distribute/distributed_file_utils.py
"""Utilities that help manage directory path in distributed settings.

In multi-worker training, the need to write a file to distributed file
location often requires only one copy done by one worker despite many workers
that are involved in training. The option to only perform saving by chief is
not feasible for a couple of reasons: 1) Chief and workers may each contain
a client that runs the same piece of code and it's preferred not to make
any distinction between the code run by chief and other workers, and 2)
saving of model or model's related information may require SyncOnRead
variables to be read, which needs the cooperation of all workers to perform
all-reduce.

This set of utility is used so that only one copy is written to the needed
directory, by supplying a temporary write directory path for workers that don't
need to save, and removing the temporary directory once file writing is done.

Example usage:
```
# Before using a directory to write file to.
self.log_write_dir = write_dirpath(self.log_dir, get_distribution_strategy())
# Now `self.log_write_dir` can be safely used to write file to.

...

# After the file is written to the directory.
remove_temp_dirpath(self.log_dir, get_distribution_strategy())

```

Experimental. API is subject to change.
"""


def _get_base_dirpath(strategy):
    task_id = strategy.extended._task_id  # pylint: disable=protected-access
    return "workertemp_" + str(task_id)


def _is_temp_dir(dirpath, strategy):
    return dirpath.endswith(_get_base_dirpath(strategy))


def _get_temp_dir(dirpath, strategy):
    if _is_temp_dir(dirpath, strategy):
        temp_dir = dirpath
    else:
        temp_dir = os.path.join(dirpath, _get_base_dirpath(strategy))
    tf.io.gfile.makedirs(temp_dir)
    return temp_dir


def write_dirpath(dirpath, strategy):
    """Returns the writing dir that should be used to save file distributedly.

    `dirpath` would be created if it doesn't exist.

    Args:
        dirpath: Original dirpath that would be used without distribution.
        strategy: The tf.distribute strategy object currently used.

    Returns:
        The writing dir path that should be used to save with distribution.
    """
    if strategy is None:
        # Infer strategy if not given.
        strategy = tf.distribute.get_strategy()
    if strategy is None:
        # If strategy is still not available, this is not in distributed training.
        # Fallback to original dirpath.
        return dirpath
    if (
        not strategy.extended._in_multi_worker_mode()
    ):  # pylint: disable=protected-access
        return dirpath
    if strategy.extended.should_checkpoint:
        return dirpath
    # If this worker is not chief and hence should not save file, save it to a
    # temporary directory to be removed later.
    return _get_temp_dir(dirpath, strategy)


def remove_temp_dirpath(dirpath, strategy):
    """Removes the temp path after writing is finished.

    Args:
        dirpath: Original dirpath that would be used without distribution, or
            the temporary dirpath used with distribution.
        strategy: The tf.distribute strategy object currently used.
    """
    if strategy is None:
        # Infer strategy if not given.
        strategy = tf.distribute.get_strategy()
    if strategy is None:
        # If strategy is still not available, this is not in distributed training.
        # Fallback to no-op.
        return
    # TODO(anjalisridhar): Consider removing the check for multi worker mode since
    # it is redundant when used with the should_checkpoint property.
    if (
        strategy.extended._in_multi_worker_mode()
        and not strategy.extended.should_checkpoint
    ):
        # If this worker is not chief and hence should not save file, remove
        # the temporary directory.
        tf.io.gfile.rmtree(_get_temp_dir(dirpath, strategy))


def write_filepath(filepath, strategy):
    """Returns the writing file path to be used to save file distributedly.

    Directory to contain `filepath` would be created if it doesn't exist.

    Args:
        filepath: Original filepath that would be used without distribution.
        strategy: The tf.distribute strategy object currently used.

    Returns:
        The writing filepath that should be used to save file with distribution.
    """
    dirpath = os.path.dirname(filepath)
    base = os.path.basename(filepath)
    return os.path.join(write_dirpath(dirpath, strategy), base)


def remove_temp_dir_with_filepath(filepath, strategy):
    """Removes the temp path for file after writing is finished.

    Args:
        filepath: Original filepath that would be used without distribution, or
            the temporary filepath used with distribution.
        strategy: The tf.distribute strategy object currently used.
    """
    remove_temp_dirpath(os.path.dirname(filepath), strategy)
