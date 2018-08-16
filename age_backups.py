#!/usr/bin/env python3

# pylint: disable=too-many-lines

"""Tag images/snapshots for deletion, based on retention policy

https://github.com/sqlxpert/aws-tag-sched-ops/

Copyright 2018, Paul Marcelin

This file is part of TagSchedOps.

TagSchedOps is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

TagSchedOps is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with TagSchedOps. If not, see http://www.gnu.org/licenses/

SECURITY WARNINGS:

This program applies an interval-based retention policy, but
it cannot act on images/snapshots that do not exist. It is
your responsibility to ensure that images/snapshots from
each interval that you specify are actually available.

The minimum privileges required by this program cannot be
used to delete images/snapshots, but only to tag them for
deletion. These privileges can be used, accidentally or
intentionally, to tag ALL images/snapshots for deletion.
It is your responsibility to incorporate data loss prevention
safeguards into your manual or automated deletion procedure.

Due to an AWS IAM/RDS limitation, the minimum privileges
that this program requires can be used to manipulate tags
in addition to 'managed-delete', on RDS snapshots.

To execute directly:

1. Running in EC2, with an IAM role, is recommded for better security.
   If running on a local system, have a dedicated IAM user with an AWS API
   key ("Programmatic access") but no password (no "AWS Management Console
   access") and no attached IAM policies (certainly not AdministratorAccess).
2. Complete the Python 3 environment setup steps in requirements.txt
3a. If running in EC2:
    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html
    Add an IAM role to the instance. No AWS API key is needed.
-OR-
3b. If running on a local system:
    http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html#cli-quick-configuration
    Follow the AWS command-line interface (CLI) configuration prompts to save
    the IAM user's AWS API Key ID and Secret Key locally, and set a region:
      aws configure  # Consider --profile (see Named Profiles in linked doc.)
4. Attach the RdsTagSchedOpsTagForDeletion and Ec2TagSchedOpsTagForDeletion
   IAM policies to the IAM role (if running in EC2) or to the IAM user (if
   running on a local system). No other policies should be attached.
5. Fix file permissions:
     chmod --changes a+x age_backups.py
6. At the start of each session, activate your Python 3 virtual environment.
7. If running on an EC2 instance, also set a region each time:
     export AWS_DEFAULT_REGION='us-east-1'
   Optionally, EC2 users too can set this once and for all, using the AWS CLI:
     aws configure set region 'us-east-1'
8. Run the program, and see available options:
     ./age_backups.py --help

For delevopers only:

# pylint: disable=line-too-long

1. Check Python syntax and style (must use Python 3 Pylint and pycodestyle!):
     deactivate
     source VIRTUALENV_PATH/bin/activate
     cd aws-tag-sched-ops  # Home of pylintrc and pycodestyle setup.cfg
     pylint      age_backups.py
     pycodestyle age_backups.py
2. Create a minimal Python 3 virtual environment, at VIRTUALENV_TINY_PATH,
   only for AWS Lambda packaging (no developer tools, which are unnecessary
   at run-time, and no botocore or boto3, which are always provided by AWS):
     deactivate
     python3 -m venv VIRTUALENV_TINY_PATH
     source VIRTUALENV_MIN_PATH/bin/activate
     pip3 install --upgrade pytz python-dateutil aniso8601
   For details and an example, see:
   https://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html#deployment-pkg-for-virtualenv
3. Package for upload to S3, for use with AWS Lambda:
     deactivate
     source VIRTUALENV_TINY_PATH/bin/activate
     cd aws-tag-sched-ops
     rm --force             /tmp/age_backups.py.zip
     zip                    /tmp/age_backups.py.zip age_backups.py
     cd "${VIRTUAL_ENV}/lib/python3.6/site-packages"
     zip --recurse-paths -8 /tmp/age_backups.py.zip * --exclude '*.pyc' '*/__pycache__/'
     cd -
     md5sum                 /tmp/age_backups.py.zip > aws-lambda/age_backups.py.zip.md5.txt
     mv --force             /tmp/age_backups.py.zip   aws-lambda
"""

import os
import argparse
import collections
import re
import datetime
import pytz
import dateutil   # pylint: disable=unused-import
import aniso8601  # uses dateutil!
import boto3
import botocore


DEBUG = ("DEBUG" in os.environ)  # Print details if set


# Leave empty, so inadvertent execution does no harm:
RETAIN_POLICY_DEFAULT = [
  # "R31/P1D",  # Keep first daily snapshots for past 31 days
]
TAG_DEL = "managed-delete"
TAGS_DICT_DEL = {TAG_DEL: ""}
LOG_LINE_FMT = "\t".join([
  "{code}",
  "{region}",
  "{parent_rsrc_id}",
  "{date}",
  "{rsrc_id}",
  "{op}",
  "{note}"
])


def filter_encode(filter_pair):
  """Take a (Name, Values) tuple, return a boto3 Filter dictionary.
  """

  (filter_name, filter_vals) = filter_pair
  return {"Name": filter_name, "Values": list(filter_vals)}


def tag_pairs_to_dict(tag_pairs):
  """Flatten a list of Key, Value pair dictionaries to one tags dictionary.
  """

  return {
    tag_pair["Key"]: tag_pair["Value"]
    for tag_pair in tag_pairs
  }


def tags_dict_to_pairs(tags_dict):
  """Take a tag dict, return a list of Key, Value pair dicts for boto3.
  """

  return [
    {"Key": tag_key, "Value": tag_value}
    for (tag_key, tag_value) in tags_dict.items()
  ]


PARAMS = {
  "ec2": {
    "tag_ops": {

      "get": {  # Not needed; most boto3 EC2 describe methods return tags
        "method_name": "describe_tags",
        "kwarg_keys": {
          "rsrc_id": "Filters",
        },
        "kwarg_process_fns": {
          "rsrc_id": lambda rsrc_id: [
            filter_encode(("resource-id", [rsrc_id]))
          ],
        },
        "resp_process_fn": lambda resp: tag_pairs_to_dict(resp["Tags"])
      },

      "add": {
        "method_name": "create_tags",
        "kwarg_keys": {
          "rsrc_id": "Resources",
          "tags": "Tags",
        },
        "kwarg_process_fns": {
          "rsrc_id": lambda rsrc_id: [rsrc_id],
          "tags": tags_dict_to_pairs,
        },
        "resp_process_fn": lambda resp: True,
      },

      "del": {
        "method_name": "delete_tags",
        "kwarg_keys": {
          "rsrc_id": "Resources",
          "tags": "Tags",
        },
        "kwarg_process_fns": {
          "rsrc_id": lambda rsrc_id: [rsrc_id],
          "tags": lambda tags: [{"Key": tag_key for tag_key in tags}],
        },
        "resp_process_fn": lambda resp: True,
      },

    },
    "rsrc_types": {

      "Snapshot": {
        "pager_name": "describe_snapshots",
        "describe_kwargs_base": {
          "OwnerIds": ["self"],
        },
        "filters_pre": [
          ("status", ["completed"]),
        ],
        "filters_pre_tag_key_vals_pairs": [
          ("managed-origin", ["snapshot"]),
        ],
        "descs_get": lambda resp: resp["Snapshots"],
        "desc_key_rsrc_id": "SnapshotId",
        "desc_post_filter_fn": lambda desc: True,
        "parent_rsrc_id_get": lambda desc, tags: desc["VolumeId"],
        "create_date_get": lambda desc: desc["StartTime"],
      },

      "Image": {
        "describe_method_name": "describe_images",
        "describe_kwargs_base": {
          "Owners": ["self"],
        },
        "filters_pre": [
          ("state", ["available"]),
        ],
        "filters_pre_tag_key_vals_pairs": [
          ("managed-origin", ["image", "reboot-image"]),
        ],
        "descs_get": lambda resp: resp["Images"],
        "desc_key_rsrc_id": "ImageId",
        "desc_post_filter_fn": lambda desc: True,
        "parent_rsrc_id_get": lambda desc, tags: tags["managed-parent-id"],
        "create_date_get": lambda desc: aniso8601.parse_datetime(
          desc["CreationDate"]
        ),
      },

    },
  },
  "rds": {
    "tag_ops": {

      "get": {
        "method_name": "list_tags_for_resource",
        "kwarg_keys": {
          "rsrc_id": "ResourceName",
        },
        "kwarg_process_fns": {
          "rsrc_id": lambda rsrc_id: rsrc_id,
        },
        "resp_process_fn": lambda resp: tag_pairs_to_dict(resp["TagList"])
      },

      "add": {
        "method_name": "add_tags_to_resource",
        "kwarg_keys": {
          "rsrc_id": "ResourceName",
          "tags": "Tags",
        },
        "kwarg_process_fns": {
          "rsrc_id": lambda rsrc_id: rsrc_id,
          "tags": tags_dict_to_pairs,
        },
        "resp_process_fn": lambda resp: True,
      },

      "del": {
        "method_name": "remove_tags_from_resource",
        "kwarg_keys": {
          "rsrc_id": "ResourceName",
          "tags": "TagKeys",
        },
        "kwarg_process_fns": {
          "rsrc_id": lambda rsrc_id: rsrc_id,
          # pylint: disable=unnecessary-lambda
          "tags": lambda tags: list(tags),  # Return list of tag KEYS
        },
        "resp_process_fn": lambda resp: True,
      },

    },
    "rsrc_types": {

      "DBSnapshot": {
        "pager_name": "describe_db_snapshots",
        "kwargs": {
        },
        "filters_post_tag_key_vals_pairs": [
          ("managed-origin", ["snapshot", "snapshot-stop"]),
        ],
        "descs_get": lambda resp: resp["DBSnapshots"],
        "desc_post_filter_fn": lambda desc: (
          (desc["Status"] == "available")
          and (desc["SnapshotType"] == "manual")
        ),
        "desc_key_rsrc_id": "DBSnapshotArn",
        "desc_key_rsrc_id_tag_ops": "DBSnapshotArn",
        "parent_rsrc_id_get": lambda desc, tags: desc["DBInstanceIdentifier"],
        "create_date_get": lambda desc: desc["SnapshotCreateTime"],
      },

    },
  },
}


def arg_parser_get():
  """Return an argparse parser for command-line arguments.
  """

  arg_parser = argparse.ArgumentParser(
    allow_abbrev=False,
    usage=None,  # Selects default, auto-generate
    add_help=True,
    formatter_class=argparse.RawTextHelpFormatter,
    description=
"""Tag expired EC2 images, EBS snapshots and RDS snapshots for deletion

Instructions at https://github.com/sqlxpert/tag-sched-ops

This program adds/removes the 'managed-delete' tag. It is meant to act only
on images/snapshots created by TagSchedOps, with their 'managed-' tags intact.
""",
    epilog="""Copyright 2018, Paul Marcelin.

This program is part of TagSchedOps.

TagSchedOps is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

TagSchedOps is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with TagSchedOps. If not, see http://www.gnu.org/licenses/

Instructions at https://github.com/sqlxpert/tag-sched-ops
""",
# Deliberately repeat instuction URL, in case user has no PAGER
  )
  arg_parser.add_argument(
    "--retain-intervals",
    required=not bool(RETAIN_POLICY_DEFAULT),
    nargs="+",
    metavar="INTERV",
    dest="retain_policy",
    type=str,
    default=RETAIN_POLICY_DEFAULT,
    action="store",
    help=
"""One or more ISO 8601 intervals, each repeating or non-,
and specified as a duration. For each EC2 insance, EBS
volume and RDS database, the first available image/
snapshot created during each period of an interval will
be left alone, and any others created during the period
will be tagged for deletion.

Use spaces to separate multiple intervals. No decimal
is allowed, hour must be 0-4, 6 or 12, minute must be
0, 10, 20 or 30, and second must be 0.

To keep first daily images/snapshots from the past
31 days, use:

  %(prog)s --retain-intervals 'R31/1D'

To rescue images/snapshots tagged but not yet deleted:

  %(prog)s \\
    --retain-intervals 'R/PT10M' \\
    --tag-keys 'managed-delete'

To keep first hourly images/snapshots from the past 24
hours, first daily ones from the past 7 days, first
weekly ones from the past 5 weeks, first monthly ones
from the past 12 months, and first yearly ones, from
the beginning:

  %(prog)s --retain-intervals \\
    'R24/PT1H' 'R7/P1D' 'R5/P1W' 'R12/P1M' 'R/P1Y'

If multiple images/snapshots of the same instance/
volume were created during the same 10-minute period
(abnormal for TagSchedOps), which one will be retained
is unpredictable; check output.

""",
# Final blank line fixes confusing argparse help message formatting
  )
  arg_parser.add_argument(
    "--user-timezone",
    nargs="?",
    metavar="TZ",
    dest="timezone_user_str",
    type=str,
    default="",
    action="store",
    help=
"""The Olson name of your local timezone (for example,
'America/St_Johns').

If not given, defaults to your system's local timezone.
Local time is useful if you want to find images/
snapshots created during periods aligned with your day
(which started at midnight in your timezone -- not in
London, England).

If, on the other hand, you prefer intervals aligned to
the UTC day, use:

  %(prog)s --user-timezone 'UTC'

""",
  )
  arg_parser.add_argument(
    "--tag-keys",
    nargs="+",
    metavar="KEY",
    dest="tag_keys_lists",
    type=str,
    default=[],
    action="append",
    help=
"""One or more tag keys. The image/snapshot must have at
least one of these tags (logical OR). The values of the
tags do not matter.

You may repeat --tag-key to create multiple rules
(logical AND).
""",
  )
  arg_parser.add_argument(
    "--no-tag-keys",
    nargs="+",
    metavar="KEY",
    dest="no_tag_keys",
    type=str,
    default=[],
    action="store",
    help=
"""One or more tag keys. The image/snapshot must not have
any of these tags (logical NOR).
""",
  )
  arg_parser.add_argument(
    "--tag-key-vals",
    nargs="+",
    metavar=("KEY", "VALUE"),
    dest="tag_key_vals_lists",
    type=str,
    default=[],
    action="append",
    help=
"""A tag key, optionally followed by one or more tag
values. The image/snapshot must have the tag and, if
values are given, the value of the tag must be one of
them (logical OR).

You may repeat --tag-key-vals to create multiple rules
(logical AND).
""",
  )
  arg_parser.add_argument(
    "--region",
    nargs="*",
    metavar="REGION",
    dest="regions",
    type=str,
    default=[],
    action="store",
    help=
"""Zero, one or more AWS regions in which to look for
images/snapshots.

If no region is specified, the AWS client defaults to
consulting:

* the AWS_DEFAULT_REGION environment variable

* the mainclient configuration profile;
  set this up in advance with:
    aws configure

* a specific profile named in AWS_PROFILE;
  set this up in advance with:
    aws configure --profile "${AWS_PROFILE}"

Specifying --region with no region name is allowed
so that you can use a shell array but still trigger
default AWS client behavior when it is empty. Shell
array example:

  %(prog)s --region ${my_regions[@]}

When called as an AWS Lambda function, this program
ignores the --region argument and uses the region in
which the AWS Lambda function was created.

""",
  )
  arg_parser.add_argument(
    "--dry-run",
    nargs="?",
    metavar="0|1",
    dest="dry_run",
    type=int,
    default=0,
    const=1,
    choices=(0, 1),
    action="store",
    help=
"""Show which images/snapshots would be tagged, but don't
do anything.

An optional integer is allowed so that you can toggle
this setting easily with a shell variable, instead of
adding/removing --dry-run; 0 does the real thing and
1 performs a dry run. Shell variable example:

  %(prog)s --dry-run "${dry_run}"
""",
  )
  return arg_parser


# For shorter variable names, function names, and dictionary keys, "date"
# is used even for combined date/time values. Exception: "datetime"
# is used when referring specifically to Python's datetime module.


UNITS_DATETIME_ORDERED = (
  "year",
  "month",
  # "week"  # Not supported by datetime.replace()
  "day",
  "hour",
  "minute",
  "second",
  "microsecond",
)


def units_smaller_get(unit_largest):
  """Take a date/time unit and return a list of smaller units.

  These units are datetime.replace() keyword argument names.
  Also accepts "week", even though it is not supported by replace();
  never returns "week".
  """
  if unit_largest in UNITS_DATETIME_ORDERED:
    units_smaller = (
      UNITS_DATETIME_ORDERED[UNITS_DATETIME_ORDERED.index(unit_largest) + 1:]
    )
  elif unit_largest == "week":
    # Still need to use datetime.replace() to normalize time components...
    units_smaller = units_smaller_get("day")
  else:
    units_smaller = ()
  return units_smaller


UNIT_DATETIME_VAL_MIN = {
  "month": 1,
  "day": 1,
  "hour": 0,
  "minute": 0,
  "second": 0,
  "microsecond": 0,
}


def unit_is_time(unit):
  """Take a datetime.replace() unit, return True if it's a time unit.

  Also accepts "week", even though it's not supported by datetime.replace().

  Returns None (as opposed to False) if the unit is not recognized.
  """
  if unit in ("hour", "minute", "second", "microsecond"):
    is_time = True
  elif unit in ("year", "month", "day", "week"):
    is_time = False
  else:
    is_time = None
  return is_time


def replace_kwargs_norm_get(unit_largest):
  """Take a unit, return a datetime.replace() kwargs dict for normalization.
  """

  return {
    unit_smaller: UNIT_DATETIME_VAL_MIN[unit_smaller]
    for unit_smaller in units_smaller_get(unit_largest)
  }


def date_norm(date_in, unit_largest, multiple=1, timezone_overwrite=None):
  """Normalize a snapshot or image creation datetime.

  - unit_largest indicates the most significant date/time component
    to normalize. Less-significant date/time components will be
    set to minimum (1 for a date component, 0 for a time component).
    More-significant date/time components will not be adjusted.
    unit_largest can be any unit supported by datetime.replace().
  - multiple is the period size for unit_largest. If multiple is 1
    or unit_largest is a date unit, that date/time component will
    also not be adjusted; if multiple is 2 or more and unit_largest
    is a time unit, that time component will be truncated to the
    lower period (NOT rounded to the nearer period).
  - timezone_overwrite is the tzinfo object to be applied. No time
    conversion is performed; the timezone is simply set/overwritten.
    None preserves existing timezone (or the absence of a timezone).

  Example: unit_largest="minute", multiple=10 sets microsecond and
  second to 0 and truncates minute to the lower 10-minute period, so that
  T10:36:05.000090 would become T10:30. For unit_largest="minute", you could:
  Set multiple to...          To...
  1                           Preserve the exact minute
  2-6, 10, 12, 15, 20, or 30  Divide the hour into equal groups
  60                          Zero out the minute
  (Other values for multiple would not make sense,
  because the hour would divided unequally.)
  """

  replace_kwargs = replace_kwargs_norm_get(unit_largest)
  if (multiple > 1) and unit_is_time(unit_largest):
    replace_kwargs[unit_largest] = (
      getattr(date_in, unit_largest) // multiple * multiple
    )
  if timezone_overwrite is not None:
    replace_kwargs["tzinfo"] = timezone_overwrite
  return date_in.replace(**replace_kwargs)


def create_date_aws_norm(date_in):
  """Take an AWS resource creation date/time, return normalized version.
  """

  return date_norm(
    date_in,
    "minute",
    multiple=10,  # TagSchedOps creates images/snapshots every 10 minutes
    timezone_overwrite=pytz.utc,
    # AWS resource creation times are UTC, but for some resource
    # types, the timezone comes in as an offset rather than a name,
    # so always apply the properly-identified UTC timezone.
  )


UNIT_DURATION_TO_DATETIME = {
  ("", "Y"): "year",
  ("", "M"): "month",
  ("", "W"): "week",
  ("", "D"): "day",
  ("T", "H"): "hour",
  ("T", "M"): "minute",
  ("T", "S"): "second",
}
RESOLUTION_REGEXP = re.compile(r"^P(T?)(0*[1-9][0-9]*)([YMWDHS])$")


def resolution_decode(resolution):
  """Take a resolution and return its components in a dictionary.

  A resolution is an ISO 8601 interval, non-repeating, with exactly
  one element. (Omit zero-valued elements.)

  - time_mark is "T" for a time unit, or the empty string otherwise
  - unit_duration is the ISO 8601 duration element specifier letter
    (e.g., "D" for day)
  - unit_datetime is the corresponding datetime.replace() keyword
    argument name, as a string (e.g. "day"); also returns "week",
    which is not supported by replace()

  Returns None if the resolution is invalid.
  """

  resolution_match = re.match(RESOLUTION_REGEXP, resolution)
  time_mark = resolution_match.group(1)
  magnitude = int(resolution_match.group(2))
  unit_duration = resolution_match.group(3)
  unit_datetime = UNIT_DURATION_TO_DATETIME.get(
    (time_mark, unit_duration),
    ""  # Invalid resolutions like "PT1D" (day is not a time elem) not present
  )
  return (
    {
      "magnitude": magnitude,
      "time_mark": time_mark,
      "unit_duration": unit_duration,
      "unit_datetime": unit_datetime,
    }
    if unit_datetime else
    None
  )


RESOLUTIONS_OK = (
  # Keep these in order, smallest to largest, for DEBUG printing.
  "P1Y",
  "P1M",
  "P1W",
  "P1D",
  "PT12H",
  "PT6H",
  "PT4H",
  "PT3H",
  "PT2H",
  "PT1H",
  "PT30M",
  "PT20M",
  # Inconsistent with 10-minute TagSchedOps cycle, so not supported:
  # "PT15M",
  # "PT12M",
  "PT10M",
  # Too specific, so not supported:
  # "PT1M",
  # "PT1S",
)
STRFTIME_FMT_NORM = "%Y-%m-%dT%H:%M"  # Used only with UTC
STRFTIME_FMT_YMD = "%Y-%m-%dT%H:%M:%S.%f%z"
STRFTIME_FMT_W = "%Y-W%W-1T%H:%M:%S.%f%z"
#                        |
#                        Force 1st day of week, explicitly


def period_start_strs_get(
  contain_date_in=datetime.datetime.now(),  # Local and tz-naive at first
  timezone_user=None
):
  """Take a datetime and return a dictionary of start date/time strings.

  Generates ISO 8601 combined date/time strings for the start of
  various periods containing the given date/time (typically, now -->
  first day of this month, first day of this week, first hour of today,
  etc.).

  The key is the ISO 8601 duration string for the period, which will
  correspond to the resolution (smallest increment) of other durations.
  """

  contain_date = contain_date_in.astimezone(**(
    {"tz": timezone_user}
    if timezone_user else
    {}
  ))
  period_start_strs = {}
  for resolution in RESOLUTIONS_OK:
    resolution_dict = resolution_decode(resolution)
    unit = resolution_dict["unit_datetime"]
    replace_kwargs = replace_kwargs_norm_get(unit)
    if resolution_dict["time_mark"]:
      magnitude = resolution_dict["magnitude"]
      replace_kwargs[unit] = (
        getattr(contain_date, unit) // magnitude * magnitude
        #                       Truncate, don't round!
      )
    period_start_strs[resolution] = contain_date.replace(
      **replace_kwargs
    ).astimezone(
      tz=pytz.utc  # AWS image and snapshot creation times are UTC
    ).strftime(
      STRFTIME_FMT_W
      if unit == "week" else
      STRFTIME_FMT_YMD
    )
  return period_start_strs


# Match the valid repetition part of an ISO 8601 interval. r"R0+/" is not
# valid and would conflict with internal use of 0 for infinite repetition.
REPS_INFINITE = 0
INTERVAL_REPEAT_REGEXP = re.compile(r"^R(|0*[1-9][0-9]*)/")


def interval_reps_get(interval):
  """Take an ISO 8601 interval and return the number of repetitions, or None.

  None indicates no repetition part (interval was likely still valid), OR
  an invalid repetition part (interval was definitely invalid). Validation
  of the input as an interval is left to other functions.
  """

  reps_match = INTERVAL_REPEAT_REGEXP.match(interval)
  if reps_match:
    reps_str = reps_match.group(1)
    reps = REPS_INFINITE if reps_str == "" else int(reps_str)
  else:
    reps = None
  return reps


DURATION_ZERO_REMOVE_REGEXP = re.compile(r"(?<=[PTYMWDHM])0+[YMWDHMS]")


def duration_zero_remove(duration):
  """Remove zero-valued elements from an ISO 8601 duration within a string.

  The duration portion of the string will be removed entirely if all elements
  had a value of 0. Therefore, if the input was a duration alone, the result
  might be the empty string, and if the input was an interval containing a
  duration, the result might no longer be a valid interval. Validation of
  the input and output as intervals or durations is left to other functions.
  """

  return DURATION_ZERO_REMOVE_REGEXP.sub("", duration).strip("T")


INTERVAL_RESOLUTION_REGEXP = re.compile(
  r"(T?)[^PT0-9]*0*([1-9][0-9]*)([YMWDHMS])$"
)


def interval_resolution_get(interval):
  """Take an ISO 8601 interval and return the resolution.

  Resolution is the interval's smallest increment; it is also an
  interval string. (The string will be empty if no valid resolution
  is found. Though that means the interval was invalid, validation
  of the input as an interval is left to other functions.)
  """

  resolution_match = INTERVAL_RESOLUTION_REGEXP.search(
    duration_zero_remove(interval)
  )
  resolution = ""
  if resolution_match:
    time_mark = resolution_match.group(1)
    unit = resolution_match.group(3)
    if (time_mark, unit) in UNIT_DURATION_TO_DATETIME:
      # For time units, report original magnitude; for date units,
      # clamp at 1 (no divisibility concern with date units)
      magnitude = int(resolution_match.group(2)) if time_mark else 1
      resolution = f"P{time_mark}{magnitude}{unit}"
  return resolution


INTERVAL_PARTS_REGEXP = re.compile(r"^((R[^P/]*)/)?(P[^/]*)$")


def interval_split(interval):
  """Take an ISO 8601 interval, return a list of the parts.

  Supports only a repeating or non-repeating interval specified
  as a duration. Validation of the interval as a whole, and of
  the components, is left to other functions.

  Returns None if not a conforming interval.
  """

  interval_parts_match = INTERVAL_PARTS_REGEXP.match(interval)
  return (
    (interval_parts_match.group(2), interval_parts_match.group(3))
    if interval_parts_match else
    None
  )


def interval_process(interval_in, resolutions_ok=RESOLUTIONS_OK):
  """Take an ISO 8601 interval and return details in a dictionary.
  """

  interval = duration_zero_remove(interval_in)
  resolution = interval_resolution_get(interval)
  interval_parts = interval_split(interval)
  return (
    {
      "reps": interval_reps_get(interval),
      "duration_part": interval_parts[1],
      "resolution": resolution,
    }
    if (resolution in resolutions_ok) and (interval_parts is not None) else
    {}
  )


def interval_gen(interval_in, period_start_strs, context_forward=False):
  """Take an ISO 8601 interval and return a datetime generator.

  Only supports a repeating or non-repeating interval expressed
  as a duration.

  Gets the necessary context by determining the duration's
  resolution (smallest increment) and then looking up the
  interval's end date/time from period_start_strs.

  Returns the empty list if the interval was invalid or is not supported.
  """

  dates = []
  err_str = ""
  interval_dict = interval_process(interval_in)
  if interval_dict:
    duration_part = interval_dict["duration_part"]
    date_context_part = period_start_strs[interval_dict["resolution"]]

    # aniso8601 forces a choice between parse_interval (gives 2 datetimes)
    # and parse_repeating_interval (gives 1 datetime per repetition). To
    # get enough datetimes (cf. fenceposts) from parse_repeating_interval,
    # 1. If interval is non-repeating, repeat twice (start and end).
    # 2. If number of repetitions is infinite, keep. CALLER must limit.
    # 3. If number of repetitions is definite, add 1 extra (minimum 2).
    reps = interval_dict["reps"]
    if reps is None:
      repeat_part = "R2"
    elif reps == REPS_INFINITE:
      repeat_part = "R"
    else:
      reps += 1
      repeat_part = f"R{reps}"

    interval = (
      f"{repeat_part}/{date_context_part}/{duration_part}"
      if context_forward else
      f"{repeat_part}/{duration_part}/{date_context_part}"
    )
    print(LOG_LINE_FMT.format(
      code=9,
      region="",
      parent_rsrc_id="",
      date="",
      rsrc_id="",
      op="",
      note=f"Interval {interval_in} translation: {interval}"
    ))
    try:
      dates = aniso8601.parse_repeating_interval(interval, relative=True)
    except aniso8601.exceptions.ISOFormatError as exc:
      err_str = str(exc)
    # TODO: Remove next clause when aniso8601 bug is fixed:
    # https://bitbucket.org/nielsenb/aniso8601/issues/18/parsing-time-throw-a-valueerror-instead-of#comment-45727132
    except ValueError as exc:
      err_str = str(exc)
  else:
    err_str = (
      "Must be a valid ISO 8601 interval, repeating or non-, with a duration,"
      " no decimal, hour 0-4, 6 or 12, minute 0, 10, 20 or 30, and second 0."
    )

  if err_str:
    print(LOG_LINE_FMT.format(
      code=9,
      region="",
      parent_rsrc_id="",
      date="",
      rsrc_id="",
      op="",
      note=f"Bad interval '{interval_in}': {err_str}"
    ))

  return dates


# pylint: disable=too-many-arguments
def rsrc_tag_op(
  region,
  rsrc_id,
  op,
  params_svc,
  aws_client,
  tags=None,
  critical=False,
  dry_run=False,
):
  """Take a resource ID and get, add or delete tags.
  """

  if (
    not(rsrc_id)
    or ((op == "get") and tags)
    or ((op in ("add", "del")) and not tags)
  ):
    raise ValueError(
      "rsrc_tag_op: rsrc_id cannot be empty, tags must be omitted if op is "
      "'get', and tags cannot be empty if op is 'add' or 'del'"
    )

  params_tag_op = params_svc["tag_ops"][op]
  params_local = {
    "rsrc_id": rsrc_id,
    "tags": tags,
  }

  tag_op_kwargs = {}
  for (param_key, kwarg_key) in params_tag_op.get("kwarg_keys", {}).items():
    kwarg_process_fn = params_tag_op["kwarg_process_fns"][param_key]
    tag_op_kwargs[kwarg_key] = kwarg_process_fn(params_local[param_key])

  resp = {}
  err_str = ""
  success = dry_run
  result = False
  if not dry_run:  # Not a boto3 dry-run (not universally supported, anyway)
    try:
      resp = getattr(aws_client, params_tag_op["method_name"])(**tag_op_kwargs)
    except botocore.exceptions.ClientError as err:
      if critical:
        raise
      else:
        err_str = str(err)
    success = boto3_success(resp)
    if err_str or not success:
      print(LOG_LINE_FMT.format(
        code=int(success),
        region=region,
        parent_rsrc_id="",
        date="",
        rsrc_id=rsrc_id,
        op=f"tags_{op}",
        note=resp if resp else err_str,
      ))
      if critical:
        raise RuntimeError(f"tags_{op} failed for {rsrc_id} with {resp}")
    else:
      result = params_tag_op["resp_process_fn"](resp)

  if DEBUG:
    print(LOG_LINE_FMT.format(
      code=int(success),
      region=region,
      parent_rsrc_id="",
      date="",
      rsrc_id=rsrc_id,
      op=f"tags_{op}" + ("_dry_run" if dry_run else ""),
      note=tag_op_kwargs.get(
        params_tag_op["kwarg_keys"].get("tags", ""),
        {}
      ),
    ))

  return result


def desc_process(
  region,
  svc,
  params_rsrc_type,
  tags_get_fn,
  tags_post_filter_fn,
  rsrcs,
  desc
):  # pylint: disable=too-many-arguments
  """Take an AWS resource description and add to resource dictionary.
  """

  if params_rsrc_type["desc_post_filter_fn"](desc):
    tags = tags_get_fn(desc)
    if tags_post_filter_fn(tags):
      create_date = create_date_aws_norm(
        params_rsrc_type["create_date_get"](desc)
      )
      rsrcs[create_date][DEL][(
        region,
        svc,
        params_rsrc_type["parent_rsrc_id_get"](desc, tags),
        desc[params_rsrc_type["desc_key_rsrc_id"]]
      )] = tags


# Constants to make rsrcs references more readable:
DEL = 6
KEEP = 7
BEGIN = 2
END = 3


def boto3_success(resp):
  """Return True if a boto3 response reflects HTTP status code 200
  """

  return (
    isinstance(resp, dict)
    and (resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) == 200)
  )


def pager_get(params_rsrc_type, aws_client):
  """Returns a lambda function to get pages of resources.

  The lambda function encloses results returned by the describe_ method
  in a list to simulate a single "page", or invokes the paginator,
  if boto3 offers one. This keeps the result structure consistent even
  though boto3 (and the the underlying AWS REST API) treat resource
  types rather differently, sometimes even within the same AWS service!
  """

  describe_method_name = params_rsrc_type.get("describe_method_name", "")

  return lambda *args, **kwargs: (
    [getattr(aws_client, describe_method_name)(*args, **kwargs)]

    if describe_method_name else

    aws_client.get_paginator(
      params_rsrc_type["pager_name"]
    ).paginate(*args, **kwargs)
  )


def tags_get_get(params_svc, params_rsrc_type, region, aws_client):
  """Return a lambda function to get tags for a resouce.
  """

  desc_key_rsrc_id = params_rsrc_type.get("desc_key_rsrc_id_tag_ops", "")
  return (
    (
      lambda desc: rsrc_tag_op(
        region,
        desc[desc_key_rsrc_id],
        "get",
        params_svc,
        aws_client,
        tags=None,
        critical=True,
      )
    )
    if desc_key_rsrc_id else
    lambda desc: tag_pairs_to_dict(desc["Tags"])
  )


def tags_post_filter_fn_get(
  tag_keys_sets,
  no_tag_keys_set,
  tag_key_vals_pairs
):
  """Take lists of tag rules and return a lambda function to apply them.

  Each tag_keys_sets entry is a set of tag keys. At least one tag from each
  set must be present.

  No tag in no_tag_keys_set must be present.

  Each tag_key_vals_pairs entry is of the form (tag key, list of tag values).
  Each tag must be present, and the tag's value must match a value from the
  list (if the list is not empty).
  """

  return (
    (
      lambda tags: all([
        # Find the tag
        #              ... and ignore its value if no values are specified...
        #                                 ... or find some matching value:
        ((tag_key in tags) and (not(tag_vals) or (tags[tag_key] in tag_vals)))
        for (tag_key, tag_vals) in tag_key_vals_pairs
      ]) and (
        # Find no tag from the set:
        tags.keys().isdisjoint(no_tag_keys_set)
      ) and not any([
        # Find no tag from the set (when inverted by not any(),
        # this means that a tag from every set must be found):
        tags.keys().isdisjoint(tag_keys_set)
        for tag_keys_set in tag_keys_sets
      ])
    )
    if any((tag_keys_sets, no_tag_keys_set, tag_key_vals_pairs)) else
    lambda tags: True  # Speed optimization
  )


def intervals_process(params_user, date_min, rsrcs):
  """
  Take parameter dict and min. date, store interval dates in resource dict.

  date_min determines the date floors for unlimited repeating intervals.

  Returns the date ceiling of all of the intervals (which
  will be None if no valid, supported intervals were found).
  """

  intervals_end = None
  if date_min is not None:
    for interval_user in params_user["intervals"]:
      interval_end = None
      dates = interval_gen(interval_user, params_user["period_start_strs"])
      for boundary in dates:
        # Generator starts with latest date; store it as interval end date.
        # Generator goes back in time; store earlier dates as period begin
        # dates. Need at least 2 iterations, to store both end and beginning.
        if interval_end is None:
          interval_end = boundary
          rsrcs[boundary][END].add(interval_user)
        else:
          rsrcs[boundary][BEGIN].add(interval_user)
          if boundary < date_min:
            print(LOG_LINE_FMT.format(
              code=9,
              region="",
              parent_rsrc_id="",
              date=boundary.strftime(STRFTIME_FMT_NORM),
              rsrc_id="",
              op="",
              note=f"Interval {interval_user} floor"
            ))
            break
      if (
        (interval_end is not None)
        and ((intervals_end is None) or (intervals_end < interval_end))
      ):
        intervals_end = interval_end
  return intervals_end


def date_head_print(date, rsrcs_date, intervals_parent_rsrcs):
  """Take a resource dictionary item and print a date header if in debug mode.
  """

  if DEBUG:
    intervals_starting = rsrcs_date[BEGIN] - intervals_parent_rsrcs.keys()
    periods_starting = rsrcs_date[BEGIN] - intervals_starting
    intervals_ending = rsrcs_date[END]
    intervals_ending_str = (
      ("End " + ", ".join(intervals_ending) + "  ")
      if intervals_ending else
      ""
    )
    periods_starting_str = (
      ("Next " + ", ".join(periods_starting) + "  ")
      if periods_starting else
      ""
    )
    intervals_starting_str = (
      ("New " + ", ".join(intervals_starting) + "  ")
      if intervals_starting else
      ""
    )
    print(LOG_LINE_FMT.format(
      code=9,
      region="",
      parent_rsrc_id="",
      date=date.strftime(STRFTIME_FMT_NORM),
      rsrc_id="",
      op="",
      # pylint: disable=line-too-long
      note=f"{intervals_ending_str}{periods_starting_str}{intervals_starting_str}",
    ))


def rsrcs_print(date, rsrcs_date):
  """Take a resource dictionary date/time item, and print resources.
  """

  for act in (KEEP, DEL):
    op = "stage_to_del" if act == DEL else "stage_to_keep"
    for (region, dummy, parent_rsrc_id, rsrc_id) in rsrcs_date[act].keys():
      print(LOG_LINE_FMT.format(
        code=9,
        region=region,
        parent_rsrc_id=parent_rsrc_id,
        date="" if DEBUG else date.strftime(STRFTIME_FMT_NORM),
        # In DEBUG mode, date is in header line. Revisit this if execution or
        # logging ever become asynchronous, putting log lines out of order.
        rsrc_id=rsrc_id,
        op=op,
        note="",
      ))


def rsrcs_process(intervals_end, rsrcs):
  """Process resource dict, deciding which resources to delete or retain.
  """

  intervals_parent_rsrcs = {}  # Keys will be currently-open intervals
  # pylint: disable=too-many-nested-blocks
  # (Necessary, clearly documented, and easier to
  # follow than if separated into small functions.)
  for date in sorted(rsrcs):
    rsrcs_date = rsrcs[date]  # Couldn't use dict.items(), needed keys sorted
    date_head_print(date, rsrcs_date, intervals_parent_rsrcs)

    if date < intervals_end:

      for interval_period_starting in rsrcs_date[BEGIN]:
        # Initialize parent resource set for a new interval, or clear it for a
        # new period of an open interval (no first image/snapshot found yet):
        intervals_parent_rsrcs[interval_period_starting] = set()

      for interval_ended in rsrcs_date[END]:
        # Delete reference to an open interval that has now ended:
        del intervals_parent_rsrcs[interval_ended]

      # Loop through potentially deletable resources:
      for (
        (region, svc, parent_rsrc_id, rsrc_id),
        tags
      ) in rsrcs_date[DEL].items():
        not_yet_retained = True

        # Loop through parent resource sets for open intervals:
        for interval_parent_rsrcs in intervals_parent_rsrcs.values():
          if (region, svc, parent_rsrc_id) not in interval_parent_rsrcs:
            interval_parent_rsrcs.add((region, svc, parent_rsrc_id))
            if not_yet_retained:
              rsrcs_date[KEEP][(region, svc, parent_rsrc_id, rsrc_id)] = tags
              not_yet_retained = False

      # Subtract keep set from delete set:
      for (region, svc, parent_rsrc_id, rsrc_id) in rsrcs_date[KEEP].keys():
        rsrcs_date[DEL].pop((region, svc, parent_rsrc_id, rsrc_id), None)

    else:  # Keep all recently-created resources
      rsrcs_date[KEEP] = rsrcs_date[DEL]
      rsrcs_date[DEL] = {}

    rsrcs_print(date, rsrcs_date)


def cmd_args_interpet(cmd_args, aws_lambda=False):
  """Take parse_args() result and return a dictionary of parameters.
  """

  if DEBUG:
    print(LOG_LINE_FMT.format(
      code=9,
      region="",
      parent_rsrc_id="",
      date="",
      rsrc_id="",
      op="",
      note="Args, parsed: " + str(vars(cmd_args))
    ))

  timezone_str = cmd_args.timezone_user_str
  if timezone_str:
    timezone = pytz.timezone(timezone_str)
  else:
    timezone = None

  regions = cmd_args.regions
  if aws_lambda or not regions:
    regions = [""]  # Dummy entry lets boto3 determine a region

  params_user = {
    "timezone": timezone,
    "regions": regions,
    "tag_keys_sets": [set(tag_keys) for tag_keys in cmd_args.tag_keys_lists],
    "no_tag_keys_set": set(cmd_args.no_tag_keys),
    "tag_key_vals_pairs": [
      (tag_key_vals[0], tag_key_vals[1:])
      for tag_key_vals in cmd_args.tag_key_vals_lists
    ],
    "intervals": [interval.upper() for interval in cmd_args.retain_policy],
    "period_start_strs": period_start_strs_get(timezone_user=timezone),
    "dry_run": bool(cmd_args.dry_run),
  }

  if DEBUG:
    params_user_no_start_strs = dict(params_user)
    del params_user_no_start_strs["period_start_strs"]
    print(LOG_LINE_FMT.format(
      code=9,
      region="",
      parent_rsrc_id="",
      date="",
      rsrc_id="",
      op="",
      note=f"Args, interpreted: {params_user_no_start_strs}"
    ))
    for resolution in RESOLUTIONS_OK:
      print(LOG_LINE_FMT.format(
        code=9,
        region="",
        parent_rsrc_id="",
        date=params_user["period_start_strs"][resolution],
        rsrc_id="",
        op="",
        note=f"Start for resolution {resolution}"
      ))

  return params_user


def rsrcs_tag(params, clients, rsrcs, dry_run):
  """Take resources dictionary and add tags to/remove tags from resources.
  """

  dry_run_str = "_dry_run" if dry_run else ""
  for (date, rsrcs_date) in rsrcs.items():
    for (status, tags_test, tag_op, user_str) in (
      (DEL, lambda tags_dict: TAG_DEL not in tags_dict, "add", "tag_to_del"),
      (KEEP, lambda tags_dict: TAG_DEL in tags_dict, "del", "tag_to_keep"),
    ):
      for (
        (region, svc, parent_rsrc_id, rsrc_id),
        tags
      ) in rsrcs_date[status].items():
        if tags_test(tags):
          success = rsrc_tag_op(
            region,
            rsrc_id,
            tag_op,
            params[svc],
            clients[(region, svc)],
            tags=TAGS_DICT_DEL,
            critical=False,
            dry_run=dry_run,
          )
          print(LOG_LINE_FMT.format(
            code=int(bool(success)),
            region=region,
            parent_rsrc_id=parent_rsrc_id,
            date=date.strftime(STRFTIME_FMT_NORM),
            rsrc_id=rsrc_id,
            op=f"{user_str}{dry_run_str}",
            note="",
          ))


def describe_kwargs_get(params_rsrc_type, params_user):
  """Take user and resource type parameters, return keyword args dictionary.
  """

  tag_key_vals_pairs = (
    params_rsrc_type.get("filters_pre_tag_key_vals_pairs", [])
    + params_user["tag_key_vals_pairs"]
  )
  tag_key_sets = (
    params_rsrc_type.get("filters_pre_tag_keys_sets", [])
    + params_user["tag_keys_sets"]
  )
  if "filters_pre_tag_key_vals_pairs" in params_rsrc_type:
    filters_pre_tag_key_vals_pairs = tag_key_vals_pairs
    filters_post_tag_key_vals_pairs = []
    filters_pre_tag_keys_sets = tag_key_sets
    filters_post_tag_keys_sets = []
  else:
    filters_pre_tag_key_vals_pairs = []
    filters_post_tag_key_vals_pairs = tag_key_vals_pairs
    filters_pre_tag_keys_sets = []
    filters_post_tag_keys_sets = tag_key_sets

  describe_kwargs = dict(params_rsrc_type.get("describe_kwargs_base", {}))
  filters_pre = (
    params_rsrc_type.get("filters_pre", [])
    + [("tag-key", tag_keys) for tag_keys in filters_pre_tag_keys_sets]
    + [
      (f"tag:{tag_key}", tag_vals)
      for (tag_key, tag_vals) in filters_pre_tag_key_vals_pairs
    ]
  )
  if filters_pre:
    describe_kwargs["Filters"] = [
      filter_encode(filter) for filter in filters_pre
    ]

  tags_post_filter_fn = tags_post_filter_fn_get(
    filters_post_tag_keys_sets,
    params_user["no_tag_keys_set"],
    filters_post_tag_key_vals_pairs
  )

  return (describe_kwargs, tags_post_filter_fn)


def lambda_handler(event, context):  # pylint: disable=unused-argument
  """List matching EC2 instance images, EBS volume snapshots and RDS snapshots
  """

  print(re.sub(r"[{}]", "", LOG_LINE_FMT))  # Simple log header

  # Only when called by AWS Lambda:
  # https://docs.aws.amazon.com/lambda/latest/dg/python-programming-model-handler-types.html
  # Accept arguments via the event parameter, as a single string or as a
  # list of strings. Single-string is supported so that the same string can
  # be fed to AWS Lambda or used on a shell command-line. When passing a
  # single string, you may enclose argument words in single or double quotes
  # (' or "), for syntactic consistency with the shell command-line, but
  # if any argument contains whitespace (tag keys and values are possible
  # examples), you must pass a list of strings instead of a single string.
  aws_lambda = True
  if isinstance(event, str):
    parse_args_args = [[word.strip("'\"") for word in event.split()]]
  elif isinstance(event, list):
    parse_args_args = [event]
  else:
    aws_lambda = False
    parse_args_args = [None]  # Brings in parse_args default, sys.argv
  params_user = cmd_args_interpet(
    arg_parser_get().parse_args(*parse_args_args),
    aws_lambda=aws_lambda,
  )

  # Master resource dictionary:
  # Key is a datetime, which represent a period boundary from
  # an interval and/or the creation date of an image/snapshot.
  rsrcs = collections.defaultdict(lambda: {
    DEL: {},    # Resources created on this date, to be deleted
    KEEP: {},   # Resources created on this date, to be retained
    BEGIN: set(),  # Intervals/interval periods starting on this date
    END: set(),    # Intervals ending on this date
  })

  clients = {}
  for region in params_user["regions"]:
    for (svc, params_svc) in PARAMS.items():

      # boto3 method references can only be resolved at run-time,
      # against an instance of an AWS service's Client class.
      # http://boto3.readthedocs.io/en/latest/guide/events.html#extensibility-guide
      aws_client = boto3.client(
        svc,
        **({} if region == "" else {"region_name": region})
      )
      clients[(region, svc)] = aws_client

      for (rsrc_type, params_rsrc_type) in params_svc["rsrc_types"].items():
        pager = pager_get(params_rsrc_type, aws_client)
        tags_get_fn = tags_get_get(
          params_svc,
          params_rsrc_type,
          region,
          aws_client
        )
        (describe_kwargs, tags_post_filter_fn) = describe_kwargs_get(
          params_rsrc_type,
          params_user
        )
        if DEBUG:
          print(LOG_LINE_FMT.format(
            code=9,
            region="",
            parent_rsrc_id="",
            date="",
            rsrc_id="",
            op="",
            note=f"{svc} {rsrc_type} describe args: {describe_kwargs}"
          ))
        for page in pager(**describe_kwargs):
          for desc in params_rsrc_type["descs_get"](page):
            desc_process(
              region,
              svc,
              params_rsrc_type,
              tags_get_fn,
              tags_post_filter_fn,
              rsrcs,
              desc
            )

  created_min = min(rsrcs) if rsrcs else None
  print(LOG_LINE_FMT.format(
    code=9,
    region="",
    parent_rsrc_id="",
    date=created_min.strftime(STRFTIME_FMT_NORM) if created_min else "",
    rsrc_id="",
    op="",
    note=f"Oldest image/snapshot created"
  ))

  if created_min:
    intervals_end = intervals_process(params_user, created_min, rsrcs)
    print(LOG_LINE_FMT.format(
      code=9,
      region="",
      parent_rsrc_id="",
      date=intervals_end.strftime(STRFTIME_FMT_NORM) if intervals_end else "",
      rsrc_id="",
      op="",
      note=f"End of latest interval"
    ))
    if intervals_end:
      rsrcs_process(intervals_end, rsrcs)
      rsrcs_tag(PARAMS, clients, rsrcs, params_user["dry_run"])


if __name__ == "__main__":
  lambda_handler(None, None)
