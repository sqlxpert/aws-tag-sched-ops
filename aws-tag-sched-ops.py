#!/usr/bin/env python3
"""Perform scheduled operations on AWS resources, based on tags

Running outside AWS Lambda NOT RECOMMENDED!

https://github.com/sqlxpert/aws-tag-sched-ops/

Copyright 2022, Paul Marcelin

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

# pylint: disable=line-too-long

Developers: to run outside AWS Lambda:

 1. Have a separate AWS account number, with no production resources.

 2. Complete the Python 3 environment setup steps in requirements.txt

 3. Install the AWS Command-Line Interface
    https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html

4a. If working on an EC2 instance, create a dedicated IAM role with no
    inline or managed policies (no AdministratorAccess, etc.) and assign
    the role to the instance. When logged in to the instance, set the region:

    aws configure set region         us-east-1 --profile default

4b. If working locally rather than on an EC2 instance, create a dedicated
    IAM user with an AWS API key ("Programmatic access") but no password
    (no "AWS Management Console access") and no inline or managed policies
    (no AdministratorAccess, etc.). Save the key locally, and set the region:

    aws configure

 5. Repeat the following for Find, Do, BackupFind and BackupDelete:

    aws configure set region         us-east-1 --profile TagSchedOpsFind
    aws configure set source_profile default   --profile TagSchedOpsFind
    aws configure set role_arn \
      'arn:aws:iam::AWS_ACCOUNT:role/STACK_NAME-TagSchedOpsZLambdaFnFind-RANDOM' \
                                               --profile TagSchedOpsFind

 6. Create a CloudFormation Change Set and add one of the following Principals
    to the AssumeRolePolicyDocument, for ALL of the TagSchedOpsZLambdaFn roles:

    AWS: [ !Sub "arn:aws:iam::${AWS::AccountId}:user/IAM_USER" ]
    or
    AWS: [ !Sub "arn:aws:iam::${AWS::AccountId}:role/EC2_INSTANCE_ROLE" ]

 7. Using the AWS Console (or your regular infrastructure-as-code system),
    add an inline policy to your IAM user or EC2 instance role:

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": "sts:AssumeRole",
          "Resource": [
            "arn:aws:iam::AWS_ACCOUNT:role/STACK_NAME-TagSchedOpsZLambdaFnFind-RANDOM",
            "arn:aws:iam::AWS_ACCOUNT:role/STACK_NAME-TagSchedOpsZLambdaFnDo-RANDOM",
            "arn:aws:iam::AWS_ACCOUNT:role/STACK_NAME-TagSchedOpsZLambdaFnBackupFind-RANDOM",
            "arn:aws:iam::AWS_ACCOUNT:role/STACK_NAME-TagSchedOpsZLambdaFnBackupDelete-RANDOM"
          ]
        }
      ]
    }

 8. At the start of each session, activate your Python 3 virtual environment,
    select a default role to assume, and set required environment variables.

    export AWS_PROFILE=TagSchedOpsFind
    export AWS_TAG_SCHED_OPS_QUEUE_URL='https://sqs.REGION.amazonaws.com/AWS_ACCOUNT/STACK_NAME-TagSchedOpsSqsQueueDo-RANDOM-Main-RANDOM'
    export AWS_TAG_SCHED_OPS_QUEUE_MESSAGESIZE=1024  # bytes

 9. Run the program, choosing whichever handler you wish:

    python3 -m aws-tag-sched-ops.py lambda_hanlder_find

10. Check Python syntax and style (must use PyLint and PyCodeStyle for Python 3!):

    cd aws-tag-sched-ops  # Home of pylintrc and PyCodeStyle setup.cfg
    pylint      aws-tag-sched-ops.py
    pycodestyle aws-tag-sched-ops.py

11. Package for upload to S3, for use with AWS Lambda:
    zip -9 aws-lambda/aws-tag-sched-ops.py.zip   aws-tag-sched-ops.py
    md5sum aws-lambda/aws-tag-sched-ops.py.zip > aws-lambda/aws-tag-sched-ops.py.zip.md5.txt

12. To return to the privileges of the original IAM user or EC2 instance role
    for a moment, without changing AWS_PROFILE, reference the default profile:

    aws s3 cp aws-tag-sched-ops.py.zip S3_BUCKET --profile default
"""


import os
import datetime
import math
import re
import json
import pprint
import random
import collections
import boto3
import botocore


AWS_TAG_SCHED_OPS_DEBUG = ("AWS_TAG_SCHED_OPS_DEBUG" in os.environ)
QUEUE_URL = os.environ["AWS_TAG_SCHED_OPS_QUEUE_URL"]
QUEUE_MESSAGESIZE = int(os.environ.get("AWS_TAG_SCHED_OPS_QUEUE_MESSAGESIZE", 0))
QUEUE_FORMAT = "01"

# Rules for Schedule Tags
#
# Principle: Avoid an elaborate, custom data structure. Instead, because
# current date/time values will come from strftime, define the rules in
# an strftime format string, inserting some marker characters. Use these
# markers, which pass through strftime unchanged, to divide the strftime
# output into regular expressions, which can be matched against tag values.
#
#  &  And: delineates rules, ALL of which must be satisfied
#     (implemented as the split character; separates string
#      into three regexps, one each for day, hour and minute)
#
#  |  Or: delineates a rule's tag values, ANY ONE of which must be present
#     (implemented as the alternation operator within a regexp;
#      allows day, hour, or minute to be specified in various ways)
#
# \*  Wildcard: stands for any day of the month or any hour of the day
#     (appears as a literal character in tag values, so it must be escaped);
#     _ is also accepted, because RDS does not allow * in tag values
#
#  ~  10-minute normalization marker: causes the preceding
#     digit to be replaced with a 1-digit wildcard (for example,
#     "M=%M~" --> "M=40~" --> r"M=4\\d", which matches "M=40" through "M=49")
#
MINUTE_NORM_REGEXP = re.compile(r"0~")
SCHED_TAG_STRFTIME_FMTS = {
  "once": r"%Y-%m-%dT%H:%M~",
  "periodic": r"dTH:M=%dT%H:%M~|uTH:M=%uT%H:%M~|d=%d|d=\*|d=_|u=%u&"
              r"dTH:M=%dT%H:%M~|uTH:M=%uT%H:%M~|H:M=%H:%M~|H=%H|H=\*|H=_&"
              r"dTH:M=%dT%H:%M~|uTH:M=%uT%H:%M~|H:M=%H:%M~|M=%M~",
}
# Delimiter between schedule parts (no commas allowed in RDS tag values!):
SCHED_DELIMS = r"[, ]"
# Child resources (images and snapshots) receive a date/time tracking
# tag and the date/time string is also embedded in their names:
TRACK_TAG_STRFTIME_FMT = "%Y-%m-%dT%H:%MZ"
# Separators are desirable and safe within tag values, not resource names:
DATE_CHARS_UNSAFE_REGEXP = re.compile(r"[-:]")


def date_time_process(date_time):
  """Take a datetime and return a dict of compiled regexps, plus strings.

  The dictionary maps frequency values to lists of compiled
  regexps, to be matched against date/time schedule tags.

  The strings are normalized to the start and end of a 10-minute cycle,
  because this program is designed to be executed every 10 minutes.
  """

  sched_regexp_lists = {
    freq: [
      re.compile(fr"(^|{SCHED_DELIMS})({tag_val_part})({SCHED_DELIMS}|$)")
      # Harmlessly permissive (mix/match/repeat delimiters)
      for tag_val_part in MINUTE_NORM_REGEXP.sub(
        r"\\d",
        date_time.strftime(strftime_fmt)
      ).split("&")
    ]
    for (freq, strftime_fmt) in SCHED_TAG_STRFTIME_FMTS.items()
  }

  date_time_norm_str = date_time.strftime(TRACK_TAG_STRFTIME_FMT)
  end_epoch_str = str(
    ( int(math.trunc(date_time.timestamp())) + int(10 * 60) ) * int(1000)
  )

  return (sched_regexp_lists, date_time_norm_str, end_epoch_str)


def tag_key_join(*args, tag_prefix="managed", tag_delim="-"):
  """Take any number of strings, apply a prefix, join, and return a tag key
  """

  return tag_delim.join([tag_prefix] + list(args))


def tag_decode(tag_pair):
  """Convert a tag dictionary returned by a boto3 method to a tuple
  """

  return (tag_pair["Key"], tag_pair["Value"])


def singleton_list(item):
  """Return a one-item list.

  Not equivalent to the built-in.
  list("abc") produces ["a", "b", "c"] where this function produces ["abc"].
  """

  return [item]


def kwargs_one_rsrc(
  rsrc_id_key,
  rsrc_id_process=lambda rsrc_id: rsrc_id
):
  """Take the resource ID parameter name (key) and return a kwargs lambda fn.

  The lambda function produces the keyword argument dictionary for boto3
  methods that are called with either a single resource ID (default) or a
  list of resource IDs (set rsrc_id_process=singleton_list). Even in the latter
  case, it accepts one resource ID only, because one-at-a-time processing
  prevents all-or-nothing failures and permits more specific error reporting.
  """

  return lambda rsrc_id: {
    rsrc_id_key: rsrc_id_process(rsrc_id),
  }


def kwargs_tags_set(
  rsrc_id_key,
  rsrc_id_process=lambda rsrc_id: rsrc_id,
  tags_key="Tags"
):
  """Take the resource ID parameter name (key) and return a kwargs lambda fn.

  The lambda function produces the keyword argument dictionary for boto3 tagging
  methods, which are called with a list of tags and, generally, a list of
  resource IDs (set rsrc_id_process=singleton_list). See also kwargs_one_rsrc.
  """

  return lambda rsrc_id, tags: {
    rsrc_id_key: rsrc_id_process(rsrc_id),
    tags_key: tags,
  }


def kwargs_describe(filter_pairs):
  """Take filter pairs and return kwargs for a boto3 describe_ method.

  Only supports Filters, so far the only describe_ parameter
  that this program uses (and used only for EC2, at that).
  """

  return (
    {
      "Filters": [
        {
          "Name": filter_name,
          "Values": filter_vals
        }
        for (filter_name, filter_vals) in filter_pairs
      ],
    }
    if filter_pairs else
    {}
  )


def op_tags_filters(params_rsrc_type):
  """Returns filter pairs for operation tags on a particular resource type.

  Only useful for EC2, because boto3 and the underlying
  AWS REST API do not yet support tag-based filters for RDS.
  """

  return [
    ("tag-key", [tag_key_join(op) for op in params_rsrc_type["ops"]])
  ]


# params defines, for each supported AWS service:
#  - search conditions for parent resources (instances and volumes)
#  - operations that can be performed on matching parent resources
#  - rules for naming and tagging child resources (images and snapshots)
#
# Python lambda functions cover up AWS API inconsistencies:
#  - how many levels from response object to individual resource
#  - whether resource tags must be requested separately
#  - whether resource creation and tagging are separate actions
#  - how equivalent arguments (and response keys) are named
#  - how resources are identified, in calls and in AWS at large

PARAMS_CHILD = {
  "ec2": {

    "Image": {
      "child_name_kwargs": lambda child_name: {
        "Name": child_name,
        "Description": child_name,
        # Set both, because some AWS interfaces expose only one!
      },
      # http://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.create_image
      "name_chars_unsafe_regexp": (
        re.compile(r"[^a-zA-Z0-9\(\)\[\] \./\-'@_]")
      ),
      "name_char_fill": "X",  # Replace unsafe characters with this
      "name_len_max": 128,
      "child_id_key": "ImageId",
      "child_tag_default": True,
    },

    "Snapshot": {
      "child_name_kwargs": lambda child_name: {
        "Description": child_name,
      },
      # http://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.create_snapshot
      # No unsafe characters documented for snapshot description
      "name_len_max": 255,
      "child_id_key": "SnapshotId",
      "child_tag_default": True,
    },

  },
  "rds": {

    "DBSnapshot": {
      "child_name_kwargs": lambda child_name: {
        "DBSnapshotIdentifier": child_name,
      },
      # http://boto3.readthedocs.io/en/latest/reference/services/rds.html#RDS.Client.add_tags_to_resource
      # http://boto3.readthedocs.io/en/latest/reference/services/rds.html#RDS.Client.create_db_snapshot
      # Standard re module seems not to support Unicode character categories:
      # "name_chars_unsafe_regexp": re.compile(r"[^\p{L}\p{Z}\p{N}_.:/=+\-]"),
      # Simplification (may give unexpected results with Unicode characters):
      "name_chars_unsafe_regexp": re.compile(r"[^\w.:/=+\-]"),
      "name_char_fill": "X",
      "name_len_max": 255,
      "child_tag_default": False,
    },
  },

}

PARAMS = {
  "ec2": {
    "tags_set_method_name": "create_tags",
    "tags_set_kwargs": kwargs_tags_set("Resources",
                                       rsrc_id_process=singleton_list),
    "rsrc_types": {

      "Instance": {
        "pager_name": "describe_instances",
        "filter_pairs": [
          ("instance-state-name", ["running", "stopping", "stopped"]),
        ],
        "extra_filter_pairs": op_tags_filters,
        "rsrcs_get_fn": lambda resp: (
          instance
          for reservation in resp["Reservations"]
          for instance in reservation["Instances"]
        ),
        "id_key": "InstanceId",
        "ops": {
          "start": {
            "op_method_name": "start_instances",
            "op_kwargs": kwargs_one_rsrc("InstanceIds",
                                         rsrc_id_process=singleton_list),
          },
          "reboot": {
            "op_method_name": "reboot_instances",
            "op_kwargs": kwargs_one_rsrc("InstanceIds",
                                         rsrc_id_process=singleton_list),
          },
          "stop": {
            "op_method_name": "stop_instances",
            "op_kwargs": kwargs_one_rsrc("InstanceIds",
                                         rsrc_id_process=singleton_list),
          },
          "image": {
            "op_method_name": "create_image",
            "op_kwargs": lambda rsrc_id: {
              "InstanceId": rsrc_id,
              "NoReboot": True,
            },
            "child_rsrc_type": "Image",
            "params_child_rsrc_type": PARAMS_CHILD["ec2"]["Image"],
          },
          "reboot-image": {
            "op_method_name": "create_image",
            "op_kwargs": lambda rsrc_id: {
              "InstanceId": rsrc_id,
              "NoReboot": False,
            },
            "child_rsrc_type": "Image",
            "params_child_rsrc_type": PARAMS_CHILD["ec2"]["Image"],
          },
        },
        "op_set_to_op": {  # How to interpret combinations of operations
          frozenset(["reboot", "image"]): "reboot-image",
          frozenset(["reboot-image", "image"]): "reboot-image",
          frozenset(["reboot-image", "reboot"]): "reboot-image",
          frozenset(["reboot-image", "image", "reboot"]): "reboot-image",
          frozenset(["reboot", "stop"]): "stop",  # Next start includes boot
        },
      },
      "Volume": {
        "pager_name": "describe_volumes",
        "filter_pairs": [
          ("status", ["available", "in-use"]),
        ],
        "extra_filter_pairs": op_tags_filters,
        "rsrcs_get_fn": lambda resp: resp["Volumes"],
        "id_key": "VolumeId",
        "ops": {
          "snapshot": {
            "op_method_name": "create_snapshot",
            "op_kwargs": kwargs_one_rsrc("VolumeId"),
            "child_rsrc_type": "Snapshot",
            "params_child_rsrc_type": PARAMS_CHILD["ec2"]["Snapshot"],
          },
        },
      },

    },
  },
  "rds": {
    "tags_get_method_name": "list_tags_for_resource",
    "tags_get_rsrc_id_kwarg": "ResourceName",
    "tags_key": "TagList",

    "tags_set_method_name": "add_tags_to_resource",
    "tags_set_kwargs": kwargs_tags_set("ResourceName"),

    "rsrc_types": {

      "DBInstance": {
        "pager_name": "describe_db_instances",
        "filter_pairs": [],  # RDS supports very few Filters
        "extra_filter_pairs": lambda params_rsrc_type: [],
        "rsrcs_get_fn": lambda resp: resp["DBInstances"],
        "id_key": "DBInstanceIdentifier",
        "rsrc_tags_get_id_key": "DBInstanceArn",
        "ops": {
          "start": {
            "op_method_name": "start_db_instance",
            "op_kwargs": kwargs_one_rsrc("DBInstanceIdentifier"),
          },
          "reboot": {
            "op_method_name": "reboot_db_instance",
            "op_kwargs": lambda rsrc_id: {
              "DBInstanceIdentifier": rsrc_id,
              "ForceFailover": False,
            },
          },
          "reboot-failover": {
            "op_method_name": "reboot_db_instance",
            "op_kwargs": lambda rsrc_id: {
              "DBInstanceIdentifier": rsrc_id,
              "ForceFailover": True,
            },
          },
          "stop": {
            "op_method_name": "stop_db_instance",
            "op_kwargs": kwargs_one_rsrc("DBInstanceIdentifier"),
          },
          "snapshot": {
            "op_method_name": "create_db_snapshot",
            "op_kwargs": kwargs_one_rsrc("DBInstanceIdentifier"),
            "child_rsrc_type": "DBSnapshot",
            "params_child_rsrc_type": PARAMS_CHILD["rds"]["DBSnapshot"],
          },
          "snapshot-stop": {
            "op_method_name": "stop_db_instance",
            "op_kwargs": kwargs_one_rsrc("DBInstanceIdentifier"),
            "child_rsrc_type": "DBSnapshot",
            "params_child_rsrc_type": PARAMS_CHILD["rds"]["DBSnapshot"],
            "child_tag_default_override": True,
          },
        },
        "op_set_to_op": {
          frozenset(["snapshot", "stop"]): "snapshot-stop",
          frozenset(["snapshot-stop", "stop"]): "snapshot-stop",
          frozenset(["snapshot-stop", "snapshot"]): "snapshot-stop",
          frozenset(["snapshot-stop", "stop", "snapshot"]): "snapshot-stop",
          frozenset(["reboot", "stop"]): "stop",  # Next start includes boot
        },
      },

    },
  },
}

CAPABS_FIND = {
  "ec2": {
    "Instance": (
      "start",
      "reboot",
      "stop",
      "image",
      "reboot-image",
    ),
    "Volume": (
      "snapshot",
    ),
  },
  "rds": {
    "DBInstance": (
      "start",
      "reboot",
      "reboot-failover",
      "stop",
      "snapshot",
      "snapshot-stop",
    ),
  },
}

LOG_LINE_FMT = "\t".join([
  "{initiated}",  # See boto3_success
  "{rsrc_id}",
  "{op}",
  "{child_rsrc_type}",
  "{child}",  # child_id (ID or ARN) if known, otherwise child_name
  "{child_op}",
  "{note}"
])


# Never pass such tags to child resources:
TAG_KEYS_UNSAFE_REGEXP = re.compile(r"^((aws|ec2|rds):|managed-delete)")
TAG_VALS_UNSAFE_REGEXP = re.compile(r"^(aws|ec2|rds):")
# https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html#tag-restrictions


def unique_suffix(
  length=5,
  chars="acefgrtxy3478"  # Small but unambiguous; for a more varied charset:
  # chars=string.ascii_lowercase + string.digits
  # http://pwgen.cvs.sourceforge.net/viewvc/pwgen/src/pw_rand.c
  # https://ux.stackexchange.com/questions/21076
):
  """Return a string of randomly chosen characters
  """

  return "".join(random.choice(chars) for dummy in range(length))


def child_name_get(
  parent_id,
  parent_name_from_tag,
  date_time_str,
  params_child_rsrc_type,
  # Prefix image and snapshot names, because some sections of the
  # AWS Web Console don't expose tags ("z..." will sort after most
  # manually-created resources, and "m" stands for "managed"):
  child_name_prefix="zm",
  child_name_delim="-",
):  # pylint: disable=too-many-arguments
  """Return the best available name for an image or snapshot
  """

  child_name_tentative = child_name_delim.join([
    child_name_prefix,
    parent_name_from_tag if parent_name_from_tag else parent_id,
    date_time_str,
    unique_suffix()
  ])
  name_chars_unsafe_regexp = params_child_rsrc_type.get(
    "name_chars_unsafe_regexp",
    None
  )
  if name_chars_unsafe_regexp:
    child_name = name_chars_unsafe_regexp.sub(
      params_child_rsrc_type["name_char_fill"],
      child_name_tentative
    )
  else:
    child_name = child_name_tentative
  return child_name[:params_child_rsrc_type["name_len_max"]]


def boto3_success(resp):
  """Return True if a boto3 response reflects HTTP status code 200.

  Success, throughout this program, means that an AWS operation
  has been initiated, not necessarily that it has completed.

  It may take hours for an image or snapshot to become available.
  Checking completion is an audit function, left to other programs.
  """

  return (
    isinstance(resp, dict)
    and (resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) == 200)
  )


def queue_message_prepare(msg_in):
  """Convert to JSON and check length
  """

  msg_out = json.dumps(msg_in)
  msg_out_len = len(bytes(msg_out, "utf-8"))
  if msg_out_len > QUEUE_MESSAGESIZE:
    raise RuntimeError(
      "After conversion to JSON this message is {} bytes long,\n"
      "but QUEUE_MESSAGESIZE is only {} bytes:\n{}".format(
        msg_out_len,
        QUEUE_MESSAGESIZE,
        pprint.pformat(msg_in),
    ))
  return msg_out


def rsrc_process(rsrc, params_tags, tags_get_fn):
  """Process tags for one parent resource (instance or volume).

  Determines which operation to perform and which tags to
  pass to a child resource (image or snapshot), if applicable.
  """

  tags_match = set()
  result = {
    "ops_tentative": set(),
    "name_from_tag": "",
    "child_tags": {},
  }

  for tag_pair in tags_get_fn(rsrc):
    (tag_key, tag_val) = tag_decode(tag_pair)
    if tag_key == "Name":
      # Save (EC2) instance or volume name but do not pass to image or snapshot
      result["name_from_tag"] = tag_val
    else:
      regexps = params_tags["tag_regexps"].get(tag_key, None)
      if regexps is None:
        if not (
          TAG_KEYS_UNSAFE_REGEXP.match(tag_key)
          or TAG_VALS_UNSAFE_REGEXP.match(tag_val)
        ):
          # Pass miscellaneous tag, but only if user-created
          result["child_tags"][tag_key] = tag_val
      else:
        # Schedule tag: check whether value matches current date/time.
        # Operation-enabling tag: ignore value. Empty list accomplishes
        #   this by triggering else clause of for...else loop.
        for regexp in regexps:
          if not regexp.search(tag_val):
            break
        else:
          tags_match.add(tag_key)

  for (tags_req, op) in params_tags["tag_set_to_op"].items():
    if tags_req <= tags_match:
      result["ops_tentative"].add(op)
  result["op"] = params_tags["op_set_to_op"].get(
    frozenset(result["ops_tentative"]),
    None
  )
  # TODO: Track whether an operation is periodic or one-time. Move operation
  # combination logic here. If a periodic and a one-time operation conflict
  # (or merely coincide, if that's simpler), discard the one-time operation.

  return result


sqs_client = boto3.client("sqs")

def rsrcs_get(
  sched_regexp_lists,
  params_rsrc_type,
  pager,
  tags_get_fn,
  svc,
  rsrc_type,
  date_time_norm_str,
  end_epoch_str
):
  """Find parent resources to operate on, and send details to queue.
  """

  date_time_norm_str_safe = DATE_CHARS_UNSAFE_REGEXP.sub(
    "",
    date_time_norm_str
  )

  params_tags = {
    "tag_regexps": {},
    "tag_set_to_op": {},
    "op_set_to_op": dict(params_rsrc_type.get("op_set_to_op", {})),  # Copy!
  }
  for op in CAPABS_FIND[svc][rsrc_type]:
    tag_op = tag_key_join(op)
    # Operation-enabling tag: ignore value (see rsrc_process):
    params_tags["tag_regexps"][tag_op] = []
    # Schedule tag: regexp match on value:
    for (freq, regexps) in sched_regexp_lists.items():
      tag_op_freq = tag_key_join(op, freq)
      params_tags["tag_regexps"][tag_op_freq] = regexps
      # Require operation-enabling tag AND one schedule tag:
      params_tags["tag_set_to_op"][frozenset([tag_op, tag_op_freq])] = op
    # Single-operation identity:
    params_tags["op_set_to_op"][frozenset([op])] = op

  if AWS_TAG_SCHED_OPS_DEBUG:
    print()
    pprint.pprint(params_tags)
    print()

  id_key = params_rsrc_type["id_key"]
  for resp in pager.paginate(**kwargs_describe(
    params_rsrc_type["filter_pairs"]
    + params_rsrc_type["extra_filter_pairs"](params_rsrc_type)
  )):
    for rsrc in params_rsrc_type["rsrcs_get_fn"](resp):
      rsrc_processed = rsrc_process(rsrc, params_tags, tags_get_fn)
      op = rsrc_processed.pop("op")
      if op:
        msg = {}
        msg.update(rsrc_processed)
        del(msg["ops_tentative"])

        rsrc_id = rsrc[id_key]
        params_svc = PARAMS[svc]
        params_op = params_rsrc_type["ops"][op]
        two_step_tag = False

        child_rsrc_type = params_op.get("child_rsrc_type", "")
        if child_rsrc_type:
          params_child_rsrc_type = params_op["params_child_rsrc_type"]
          two_step_tag = params_op.get(
            "child_tag_default_override",
            params_child_rsrc_type["child_tag_default"]
          )
          if two_step_tag:
            child_tag_kwargs = params_svc["tags_set_kwargs"]
            if "child_id_key" in params_child_rsrc_type:
              msg["child_id_key"] = params_child_rsrc_type["child_id_key"]
            msg["child_tag_method_name"] = params_svc["tags_set_method_name"]

        kwargs = params_op["op_kwargs"](rsrc_id)
        if child_rsrc_type:
          child_name = child_name_get(
            rsrc_id,
            rsrc_processed["name_from_tag"],
            date_time_norm_str_safe,
            params_child_rsrc_type
          )
          kwargs.update(params_child_rsrc_type["child_name_kwargs"](child_name))
          msg["child_tags"].update({
            tag_key_join("parent-name"): rsrc_processed["name_from_tag"],
            tag_key_join("parent-id"): rsrc_id,
            tag_key_join("origin"): op,
            tag_key_join("date-time"): date_time_norm_str,
            "Name": child_name,
          })
          if not two_step_tag:
            kwargs["Tags"] = msg["child_tags"]

        msg["method_name"] = params_op["op_method_name"]
        msg["kwargs"] = kwargs
        pprint.pprint(msg)
        sqs_resp = sqs_client.send_message(
          QueueUrl=QUEUE_URL,
          MessageBody=queue_message_prepare(msg),
          MessageAttributes={
            "version": {
              "StringValue": QUEUE_FORMAT,
              "DataType": "String",
            },
            "capab": {
              "StringValue": "{}.{}.{}".format(svc, rsrc_type, op),
              "DataType": "String",
            },
            "before": {
              "StringValue": end_epoch_str,
              "DataType": "String",
            },
          },
          # TODO: Support AWS X-Ray traceability
          # MessageSystemAttributes={
          #   "AWSTraceHeader": {
          #     "StringValue": "value-string",
          #     "DataType": "String",
          #   }
          # },
        )
        if not boto3_success(sqs_resp):
          raise RuntimeError(
            "Sending message:\n{}\nto queue {}\nfailed with response\n{}".format()
          )
      elif rsrc_processed["ops_tentative"]:
        print(LOG_LINE_FMT.format(
          initiated=0,
          rsrc_id=rsrc[id_key],
          op=",".join(sorted(rsrc_processed["ops_tentative"])),
          child_rsrc_type="",
          child="",
          child_op="",
          note="OPS_UNSUPPORTED",
        ))

  return


def tags_get_two_step(
  rsrc,
  rsrc_tags_get_id_key,
  tags_get_method,
  tags_get_rsrc_id_kwarg,
  tags_key
):
  """
  Take a resource description and a tag retrieval method, and return the tags.

  Error handling: Trap and log, noting that inability to obtain tags
  means that resources with scheduled operations might be missed.
  """

  rsrc_id = rsrc[rsrc_tags_get_id_key]
  resp = {}
  err_print = ""
  try:
    resp = tags_get_method(**{
      tags_get_rsrc_id_kwarg: rsrc_id,
    })
  except botocore.exceptions.ClientError as err:
    err_print = str(err)
  success = boto3_success(resp)
  if err_print or not success:
    print(LOG_LINE_FMT.format(
      initiated=int(success),
      rsrc_id=rsrc_id,
      op="tags_get",
      child_rsrc_type="",
      child="",
      child_op="",
      note=resp if resp else err_print,
    ))

  return resp.get(tags_key, [])


def tags_get_get(params_svc, params_rsrc_type, aws_client):
  """Returns a lambda function to get tags for a resouce.
  """

  rsrc_tags_get_id_key = params_rsrc_type.get("rsrc_tags_get_id_key", "")

  return lambda rsrc: (
    tags_get_two_step(
      rsrc,
      rsrc_tags_get_id_key,
      getattr(aws_client, params_svc["tags_get_method_name"]),
      params_svc["tags_get_rsrc_id_kwarg"],
      params_svc["tags_key"]
    )

    if rsrc_tags_get_id_key else

    rsrc["Tags"]
  )


def lambda_handler_find(event, context):  # pylint: disable=unused-argument
  """Find and queue AWS resources for scheduled operations, based on tags
  """

  if AWS_TAG_SCHED_OPS_DEBUG:
    pprint.pprint(PARAMS)
    print()

  period_minutes = 10
  td = datetime.timedelta(minutes=period_minutes)
  datetime_now = datetime.datetime.now(datetime.timezone.utc)
  datetime0 = datetime.datetime.now(datetime.timezone.utc).replace(
    minute=(datetime_now.minute // period_minutes) * period_minutes,
    seconds=0,
    microseconds=0,
  )
  datetime1 = datetime0 + td
  print(datetime0, datetime_now, datetime1)
  exit(0)

      minute=int(math.trunc(now.minute / 10)) * int(10),

  now = datetime.datetime.now(datetime.timezone.utc)
  (sched_regexp_lists, date_time_norm_str, end_epoch_str) = date_time_process(
    now.replace(
      # Go down to preceding :00, :10, :20, :30, :40 or :50
      minute=int(math.trunc(now.minute / 10)) * int(10),
      second=0,
      microsecond=0,
    )
  )
  print(re.sub(r"[{}]", "", LOG_LINE_FMT))  # Simple log header
  print(LOG_LINE_FMT.format(  # Log normalized time
    initiated=9,  # Code, to distinguish this from failure (0) or success (1)
    rsrc_id="",
    op="",
    child_rsrc_type="",
    child="",
    child_op="",
    note=date_time_norm_str,
  ))

  for svc in CAPABS_FIND:
    params_svc = PARAMS[svc]
    aws_client = boto3.client(svc)

    # boto3 method references can only be resolved at run-time,
    # against an instance of an AWS service's Client class.
    # http://boto3.readthedocs.io/en/latest/guide/events.html#extensibility-guide

    tags_set_method = getattr(aws_client, params_svc["tags_set_method_name"])

    for rsrc_type in CAPABS_FIND[svc]:
      params_rsrc_type = params_svc["rsrc_types"][rsrc_type]

      tags_get_fn = tags_get_get(params_svc, params_rsrc_type, aws_client)

      ops_rsrcs = rsrcs_get(
        sched_regexp_lists,
        params_rsrc_type,
        aws_client.get_paginator(params_rsrc_type["pager_name"]),
        tags_get_fn,
        svc,
        rsrc_type,
        date_time_norm_str,
        end_epoch_str
      )

  return

def lambda_handler_do(event, context):  # pylint: disable=unused-argument
  """Perform queued scheduled operations on AWS resources
  """

  print(json.dumps(event))

  if (int(event["Records"][0]["attributes"]["SentTimestamp"])
    < int(event["Records"][0]["messageAttributes"]["before"]["stringValue"])):
    print("Timing good (within 10-minute interval)")

  # TODO: error-handling
  sqs_client.delete_message(
    QueueUrl=QUEUE_URL,
    ReceiptHandle=event["Records"][0]["receiptHandle"],
  )

  return

if __name__ == "__main__":
  lambda_handler_do(None, None)
