#!/usr/bin/env python3
"""Perform scheduled operations on AWS resources, based on tags

Intended as an AWS Lambda function. DIRECT EXECUTION NOT RECOMMENDED.
Developers: see instructions below license notice.

https://github.com/sqlxpert/aws-tag-sched-ops/

Copyright 2017, Paul Marcelin

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

To execute directly, for development purposes ONLY:

0. Have a separate AWS account number, with no production resources.
   If running on a local system, also have a dedicated IAM user with an AWS
   API key ("Programmatic access") but no password (no "AWS Management Console
   access") and no attached IAM policies (certainly not AdministratorAccess).

1. Complete the Python 3 environment setup steps in requirements.txt

2a. If running on an EC2 instance:
    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html
    Add an IAM role to the instance. No AWS API key is needed.
-OR-
2b. If running on a local system:
    http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html#cli-quick-configuration
    Follow the AWS command-line interface (CLI) configuration prompts to save
    the IAM user's AWS API Key ID and Secret Key locally, and set a region:
      aws configure  # Consider --profile (see Named Profiles in linked doc.)

3. Attach the Ec2TagSchedOpsPerform and RdsTagSchedOpsPerform IAM policies
   to the IAM role (if running on an EC2 instance) or to the IAM user (if
   running on a local system). Attach no other policies to the role or user.

4. At the start of each session, activate your Python 3 virtual environment.

5. If running on an EC2 instance, also set a region each time:
     export AWS_DEFAULT_REGION='us-east-1'
   Optionally, EC2 users too can set this once and for all, using the AWS CLI:
     aws configure set region 'us-east-1'

6. Run the code:
     python3 aws_tag_sched_ops_perform.py

7. Check Python syntax and style (must use Python 3 PyLint and PyCodStyle!):
     cd aws-tag-sched-ops  # Home of pylintrc and PyCodeStyle setup.cfg
     pylint      aws_tag_sched_ops_perform.py
     pycodestyle aws_tag_sched_ops_perform.py

8. Package for upload to S3, for use with AWS Lambda:
     rm     aws_tag_sched_ops_perform.py.zip
     zip    aws_tag_sched_ops_perform.py.zip aws_tag_sched_ops_perform.py
     md5sum aws_tag_sched_ops_perform.py.zip
"""


import os
import datetime
import re
import pprint
import random
import collections
import boto3
import botocore


# If set (regardless of value), print parent_params internal reference dict:
DEBUG = ("DEBUG" in os.environ)

# Rules for Schedule Tags
#
# Principle: Avoid specifying allowable combinations of schedule tag values
# in some elaborate data structure. Instead, because current date/time
# values will come from strftime, define the rules in an strftime format
# string, inserting marker characters for logical operations. Use these
# markers, which pass through strftime unchanged, to divide the strftime
# output into regular expressions, which can be matched against tag values.
#
#  &  And: delineates rules, ALL OF WHICH must be satisfied
#     (implemented as the split character; separates string into three regexps,
#      one each for day, hour and minute)
#
#  |  Or: delineates a rule's tag values, ANY ONE OF WHICH must be satisfied
#     (implemented as the alternation operator within a regexp; allows
#      day, hour, or minute to be specified in various ways)
#
# \*  Wildcard: stands for any day of the month, day of the week, or hour
#     (appears as a literal character in tag values, so it must be escaped)
#
#  ~  10-minute normalization marker: causes the preceding
#     digit to be replaced with a 1-digit wildcard (for example,
#     "M=%M~" --> "M=40~" --> r"M=4\d", which matches "M=40" through "M=49")
#
MINUTE_NORM_REGEXP = re.compile(r"\d~")
SCHED_TAG_STRFTIME_FMTS = {
  # CONVENTION: frequency (freq) is the key of this dictionary.
  "once": r"%Y-%m-%dT%H:%M~",
  "periodic": r"dTH:M=%dT%H:%M~|uTH:M=%uT%H:%M~|d=%d|d=\*|u=%u&"
              r"dTH:M=%dT%H:%M~|uTH:M=%uT%H:%M~|H:M=%H:%M~|H=%H|H=\*&"
              r"dTH:M=%dT%H:%M~|uTH:M=%uT%H:%M~|H:M=%H:%M~|M=%M~",
}
# Child resources (images and snapshots) receive a date/time tracking tag
# (see TAGS_SPC), and the date/time string is also embedded in their names:
TRACK_TAG_STRFTIME_FMT = "%Y-%m-%dT%H:%M~"
# Separators are desirable and/or safe within tag values, not resource names:
TRACK_TAG_CHARS_UNSAFE_REGEXP = re.compile(r"[-:]")


def date_time_process(date_time):
  """Take a datetime and return a dict of compiled regexps, plus a string.

  The dictionary maps frequency values to lists of compiled
  regexps, to be matched against date/time schedule tags.

  The date/time string is normalized to the start of a 10-minute cycle,
  because this code is designed to be executed every 10 minutes.
  """

  sched_regexp_lists = {
    freq: [
      re.compile(r"(^|,)(" + tag_val_part + r")(,|$)")
      for tag_val_part in MINUTE_NORM_REGEXP.sub(
        r"\d",
        date_time.strftime(strftime_fmt)
      ).split("&")
    ]
    for (freq, strftime_fmt) in SCHED_TAG_STRFTIME_FMTS.items()
  }

  date_time_norm_str = MINUTE_NORM_REGEXP.sub(
    "0",
    date_time.strftime(TRACK_TAG_STRFTIME_FMT)
  )

  return (sched_regexp_lists, date_time_norm_str)


LOG_LINE_FMT = "\t".join([
  "{initiated}",  # See boto3_success
  "{svc}",
  "{rsrc_type}",
  "{rsrc_id}",
  "{op}",
  "{child_rsrc_type}",
  "{child}",  # child_id (ID or ARN) if known, otherwise child_name
  "{child_op}",
  "{note}"
])

# For most boto3 methods and responses:
TAGS_KWARG = "Tags"
TAGS_KEY = "Tags"

TAGS_UNSAFE_REGEXP = re.compile(r"^((aws|ec2|rds):|managed-delete)")


def tag_join(*args, tag_prefix="managed", tag_delim="-"):
  """Take any number of strings, apply a prefix, join, and return a tag key
  """

  return tag_delim.join([tag_prefix] + list(args))


TAGS_SPC = {
  "NAME": "Name",
  "PARENT_NAME": tag_join("parent-name"),
  "PARENT_ID": tag_join("parent-id"),
  "ORIGIN": tag_join("origin"),
  "DATE_TIME": tag_join("date-time"),
}


def filter_make(filter_name, filter_values):
  """Return a Filter dictionary for a boto3 describe_ method
  """

  return {"Name": filter_name, "Values": filter_values}


# pylint: disable=invalid-name
# (This is a global variable, not a constant)
parent_params = {
  "ec2": {  # CONVENTION: AWS service (svc)
    "Instance": {  # CONVENTION: AWS resource type (rsrc_type)
      "boto3_filters": [
        filter_make("instance-state-name", ["running", "stopping", "stopped"]),
      ],
      "pager": "describe_instances",
      "describe_key_outer": "Reservations",  # Empty string, if no outer level
      "id_key": "InstanceId",  # Inner level
      "describe_omits_tags": False,  # Does describe_ method return tags?
      "tags_get_method": None,  # Set at run-time, if applicable
      "tags_get_id_kwarg": "",
      "tags_get_id_key": "",
      "tags_get_resp_key": "",
      "ops": {
        "start": {  # CONVENTION: Supported operation (op)
          "method": None,  # Set at run-time
          "id_list": True,  # Does operation method accept multiple IDs?
          "op_kwargs": {},
          "child_rsrc_type": "",  # Kind of child created (if any)
          "two_step_tag": False,  # Follow-up tagging call after create_ call?
        },
        "reboot": {
          "method": None,
          "id_list": True,
          "op_kwargs": {},
          "child_rsrc_type": "",
          "two_step_tag": False,
        },
        "stop": {
          "method": None,
          "id_list": True,
          "op_kwargs": {},
          "child_rsrc_type": "",
          "two_step_tag": False,
        },
        "image": {
          "method": None,
          "id_list": False,
          "op_kwargs": {
            "NoReboot": True,
          },
          "child_rsrc_type": "Image",
          "two_step_tag": True,
        },
        "reboot-image": {
          "method": None,
          "id_list": False,
          "op_kwargs": {},
          "child_rsrc_type": "Image",
          "two_step_tag": True,
        },
      },
      "ops_to_op": {  # How to interpret combinations of operations
        frozenset(["reboot", "image"]): "reboot-image",
        frozenset(["reboot-image", "image"]): "reboot-image",
        frozenset(["reboot-image", "reboot"]): "reboot-image",
        frozenset(["reboot-image", "image", "reboot"]): "reboot-image",
        frozenset(["reboot", "stop"]): "stop",  # Next start includes boot
      },
    },
    "Volume": {
      "boto3_filters": [
        filter_make("status", ["available", "in-use"]),
      ],
      "pager": "describe_volumes",
      "describe_key_outer": "",
      "id_key": "VolumeId",
      "describe_omits_tags": False,
      "tags_get_method": None,
      "tags_get_id_kwarg": "",
      "tags_get_id_key": "",
      "tags_get_resp_key": "",
      "ops": {
        "snapshot": {
          "method": None,
          "id_list": False,
          "op_kwargs": {},
          "child_rsrc_type": "Snapshot",
          "two_step_tag": True,
        },
      },
      "ops_to_op": {},
    },
  },
  "rds": {
    "DBInstance": {
      "boto3_filters": [],  # RDS supports very, very few filters!
      "pager": "describe_db_instances",
      "describe_key_outer": "",
      "id_key": "DBInstanceIdentifier",
      "describe_omits_tags": True,
      "tags_get_method": None,
      "tags_get_id_kwarg": "ResourceName",
      "tags_get_id_key": "DBInstanceArn",
      "tags_get_resp_key": "TagList",
      "ops": {
        "start": {
          "method": None,
          "id_list": False,
          "op_kwargs": {},
          "child_rsrc_type": "",
          "two_step_tag": False,
        },
        "reboot": {
          "method": None,
          "id_list": False,
          "op_kwargs": {},
          "child_rsrc_type": "",
          "two_step_tag": False,
        },
        "reboot-failover": {
          "method": None,
          "id_list": False,
          "op_kwargs": {
            "ForceFailover": True,
          },
          "child_rsrc_type": "",
          "two_step_tag": False,
        },
        "stop": {
          "method": None,
          "id_list": False,
          "op_kwargs": {},
          "child_rsrc_type": "",
          "two_step_tag": False,
        },
        "snapshot": {
          "method": None,
          "id_list": False,
          "op_kwargs": {},
          "child_rsrc_type": "DBSnapshot",
          "two_step_tag": False,
        },
        "snapshot-stop": {
          "method": None,
          "id_list": False,
          "op_kwargs": {},
          "child_rsrc_type": "DBSnapshot",
          "two_step_tag": True,
        },
      },
      "ops_to_op": {
        frozenset(["snapshot", "stop"]): "snapshot-stop",
        frozenset(["snapshot-stop", "stop"]): "snapshot-stop",
        frozenset(["snapshot-stop", "snapshot"]): "snapshot-stop",
        frozenset(["snapshot-stop", "stop", "snapshot"]): "snapshot-stop",
        frozenset(["reboot", "stop"]): "stop",  # Next start includes boot
      },
    },
  },
}

# pylint: disable=invalid-name
# (This is a global variable, not a constant.)
child_params = {
  "ec2": {
    "Image": {
      # Where to store child name (two argument keywords are listed if AWS
      # supports separate name and description metadata fields for this child
      # resource type; set both, because some interfaces only expose one):
      "name_kwargs": ("Name", "Description"),
      # http://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.create_image
      "name_chars_unsafe_regexp_use": True,  # Check it for unsafe characters?
      "name_chars_unsafe_regexp": re.compile(r"[^a-zA-Z0-9\(\)\[\] \./\-'@_]"),
      "name_char_fill": "X",  # Replace unsafe characters with this
      "name_len_max": 128,
      "child_id_key": "ImageId",
      "two_step_tag_method": None,
      "two_step_tag_id_list": True,
      "two_step_tag_id_kwarg": "Resources",
    },
    "Snapshot": {
      "name_kwargs": ("Description",),
      # http://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.create_snapshot
      "name_chars_unsafe_regexp_use": False,  # No rules in documentation!
      "name_chars_unsafe_regexp": None,
      "name_char_fill": "X",
      "name_len_max": 255,
      "child_id_key": "SnapshotId",
      "two_step_tag_method": None,
      "two_step_tag_id_list": True,
      "two_step_tag_id_kwarg": "Resources",
    },
  },
  "rds": {
    "DBSnapshot": {
      "name_kwargs": ("DBSnapshotIdentifier",),
      # http://boto3.readthedocs.io/en/latest/reference/services/rds.html#RDS.Client.add_tags_to_resource
      # http://boto3.readthedocs.io/en/latest/reference/services/rds.html#RDS.Client.create_db_snapshot
      "name_chars_unsafe_regexp_use": True,
      # Standard re module seems not to support Unicode character categories:
      # "name_chars_unsafe_regexp": re.compile(r"[^\p{L}\p{Z}\p{N}_.:/=+\-]"),
      # Simplification (may give unexpected results with Unicode characters):
      "name_chars_unsafe_regexp": re.compile(r"[^\w.:/=+\-]"),
      "name_char_fill": "X",
      "name_len_max": 255,
      "child_id_key": "SPC_RDS_DERIVE_FROM_DB_ARN",
      "two_step_tag_method": None,
      "two_step_tag_id_list": False,
      "two_step_tag_id_kwarg": "ResourceName",
    },
  },
}


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


def tag_pair_encode(tag_key, tag_val):
  """Return a Tag dictionary, to be passed to a boto3 method
  """

  return {"Key": tag_key, "Value": tag_val}


def tag_pair_decode(tag_pair):
  """Convert a boto3-style Tag dictionary to a tuple
  """

  return (tag_pair["Key"], tag_pair["Value"])


def child_name_get(
  parent_id,
  parent_name_from_tag,
  date_time_str,
  child_params_rsrc_type,
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
  if child_params_rsrc_type["name_chars_unsafe_regexp_use"]:
    child_name = child_params_rsrc_type["name_chars_unsafe_regexp"].sub(
      child_params_rsrc_type["name_char_fill"],
      child_name_tentative
    )
  else:
    child_name = child_name_tentative
  return child_name[:child_params_rsrc_type["name_len_max"]]


def rsrc_process(rsrc, parent_params_rsrc_type):
  """Process Tags in one parent resource (instance or volume) dictionary.

  Determines which operation to perform and which tags to pass to a child
  resource (image or snapshot), if applicable.
  """

  tags_match = set()
  result = {
    "ops_tentative": set(),
    "name_from_tag": "",
    "child_tags": [],
  }

  for tag_pair in rsrc.get(TAGS_KEY, []):
    (tag_key, tag_val) = tag_pair_decode(tag_pair)
    if tag_key == TAGS_SPC["NAME"]:
      # Save (EC2) instance or volume name but do not pass to image or snapshot
      result["name_from_tag"] = tag_val
    else:
      regexps = parent_params_rsrc_type["sched_regexps"].get(tag_key, None)
      if regexps is None:
        if not TAGS_UNSAFE_REGEXP.match(tag_key):
          # Pass miscellaneous tag, but only if user-created
          result["child_tags"].append(tag_pair_encode(tag_key, tag_val))
      else:
        # Schedule tag: check whether value matches current date/time.
        # Operation-enabling tag: ignore value. Empty list accomplishes
        #   this by triggering else clause of for...else loop.
        for regexp in regexps:
          if not regexp.match(tag_val):
            break
        else:
          tags_match.add(tag_key)

  for (tags_req, op) in parent_params_rsrc_type["tags_to_op"].items():
    if tags_req <= tags_match:
      result["ops_tentative"].add(op)
  result["op"] = parent_params_rsrc_type["ops_to_op"].get(
    frozenset(result["ops_tentative"]),
    None
  )

  return result


def boto3_success(resp):
  """Return True if a boto3 response reflects HTTP status code 200.

  Success, throughout this code, means that an AWS operation
  has been initiated, not necessarily that it has completed.

  It may take hours for image or snapshot to become available, and checking
  for completion is an audit function, to be performed by other code or tools.
  """

  return (
    isinstance(resp, dict)
    and (resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) == 200)
  )


def rsrc_generate(describe_resp, svc, rsrc_type):
  """Yield successive parent resource (instance or volume) dictionaries.

  Accommodates inconsistencies in the structure of boto3
  describe_ method responses for different AWS resource types:
   - how many levels from top dictionary to list of resources
   - whether tags are returned, or must be requested separately

  Error-handling is minimal, because execution could not continue if a boto3
  exception occurred at this stage (i.e., while building the resource list).
  """

  describe_omits_tags = parent_params[svc][rsrc_type]["describe_omits_tags"]
  tags_get_method = parent_params[svc][rsrc_type]["tags_get_method"]
  tags_get_id_key = parent_params[svc][rsrc_type]["tags_get_id_key"]
  tags_get_id_kwarg = parent_params[svc][rsrc_type]["tags_get_id_kwarg"]
  tags_get_resp_key = parent_params[svc][rsrc_type]["tags_get_resp_key"]

  key_outer = parent_params[svc][rsrc_type]["describe_key_outer"]
  key_inner = rsrc_type + "s"

  list_outer = (
    describe_resp.get(key_outer, []) if key_outer else [describe_resp]
  )
  for dict_outer in list_outer:
    list_inner = dict_outer.get(key_inner, [])
    for rsrc in list_inner:
      if describe_omits_tags:
        tags_get_resp = tags_get_method(**{
          tags_get_id_kwarg: rsrc[tags_get_id_key],
        })
        if boto3_success(tags_get_resp):
          rsrc[TAGS_KEY] = tags_get_resp[tags_get_resp_key]
        else:
          raise Exception(
            "Could not get tags for AWS resource; boto3 response: {}".format(
              tags_get_resp
            )
          )
      yield rsrc


def rsrcs_get(
  parent_params_rsrc_type,
  svc,
  rsrc_type,
  aws_client
):
  """Return a hierarchical dict: operation --> resource ID --> details.

  Innermost dictionaries contain parent resource details,
  including tags to pass to child resources.
  """

  id_key = parent_params_rsrc_type["id_key"]
  rsrcs = collections.defaultdict(dict)
  pager = aws_client.get_paginator(parent_params_rsrc_type["pager"])
  for page in pager.paginate(Filters=parent_params_rsrc_type["boto3_filters"]):
    for rsrc in rsrc_generate(page, svc, rsrc_type):
      rsrc_processed = rsrc_process(rsrc, parent_params_rsrc_type)
      op = rsrc_processed.pop("op")
      if op:
        rsrcs[op][rsrc[id_key]] = rsrc_processed
      elif rsrc_processed["ops_tentative"]:
        print(LOG_LINE_FMT.format(
          initiated=0,  # 0 is shorter than "False", etc.
          svc=svc,
          rsrc_type=rsrc_type,
          rsrc_id=rsrc[id_key],
          op=",".join(sorted(rsrc_processed["ops_tentative"])),
          child_rsrc_type="",
          child="",
          child_op="",
          note="OPS_UNSUPPORTED",
        ))

  return rsrcs


def child_id_get(resp, child_name, svc, child_rsrc_type):
  """Take a boto3 response and return the ID of the new resource.

  Do not use for an RDS database snapshot created by create_db_snapshot.
  That boto3 method supports one-step tagging, so there is no need to
  look up the identifier of the new snapshot.

  For an RDS database snapshot created by stop_db_instance, the boto3
  response does not identify the snapshot. The name of the snapshot,
  child_name, is used to construct its identifier, which is an ARN.
  """

  child_id_key = child_params[svc][child_rsrc_type]["child_id_key"]
  if child_id_key == "SPC_RDS_DERIVE_FROM_DB_ARN" and child_name:
    parent_arn = resp.get("DBInstance", {}).get("DBInstanceArn", "")
    if parent_arn:
      arn_parts = parent_arn.split(":")
      arn_parts[-2] = "snapshot"
      arn_parts[-1] = child_name
      child_id = ":".join(arn_parts)
    else:
      child_id = ""
  else:
    child_id = resp.get(child_id_key, "")
  return child_id


def child_tags_to_add(
  parent_id,
  parent_name_from_tag,
  child_name,
  op,
  date_time_str
):
  """Return a list of additional tags for an image or snapshot
  """

  tag_spc_key_val_pairs = [
    ("PARENT_ID", parent_id),
    ("ORIGIN", op),
    ("DATE_TIME", date_time_str),
    ("NAME", child_name),
  ]
  if parent_name_from_tag:
    tag_spc_key_val_pairs.append(("PARENT_NAME", parent_name_from_tag))
  return [
    tag_pair_encode(TAGS_SPC[tag_spc_key], tag_val)
    for (tag_spc_key, tag_val) in tag_spc_key_val_pairs
  ]


def methods_set(svc, aws_client):
  """Set all method references for a given AWS service.

  Due to the design of boto3, method references must be resolved at run-time,
  against a particular instance of an AWS service's Client class. See:
  http://boto3.readthedocs.io/en/latest/guide/events.html#extensibility-guide
  """

  if svc == "ec2":
    method_tuples = (
      ("Instance", "start", aws_client.start_instances),
      ("Instance", "reboot", aws_client.reboot_instances),
      ("Instance", "stop", aws_client.stop_instances),
      ("Instance", "image", aws_client.create_image),
      ("Instance", "reboot-image", aws_client.create_image),
      ("Volume", "snapshot", aws_client.create_snapshot),
    )
    child_two_step_tag_method = aws_client.create_tags
  elif svc == "rds":
    for parent_params_rsrc_type in parent_params[svc].values():
      parent_params_rsrc_type["tags_get_method"] = (
        aws_client.list_tags_for_resource
      )
    method_tuples = (
      ("DBInstance", "snapshot", aws_client.create_db_snapshot),
      ("DBInstance", "start", aws_client.start_db_instance),
      ("DBInstance", "reboot", aws_client.reboot_db_instance),
      ("DBInstance", "reboot-failover", aws_client.reboot_db_instance),
      ("DBInstance", "stop", aws_client.stop_db_instance),
      ("DBInstance", "snapshot-stop", aws_client.stop_db_instance),
    )
    child_two_step_tag_method = aws_client.add_tags_to_resource
  for (rsrc_type, op, method) in method_tuples:
    parent_params[svc][rsrc_type]["ops"][op]["method"] = method
  for child_params_rsrc_type in child_params[svc].values():
    child_params_rsrc_type["two_step_tag_method"] = child_two_step_tag_method
  return


def methods_clr(svc):
  """Clear all method references for a given AWS service
  """

  for parent_params_rsrc_type in parent_params[svc].values():
    if svc == "rds":
      parent_params_rsrc_type["tags_get_method"] = None
    for parent_params_op in parent_params_rsrc_type["ops"].values():
      parent_params_op["method"] = None
  for child_params_rsrc_type in child_params[svc].values():
    child_params_rsrc_type["two_step_tag_method"] = None
  return


def child_tag(rsrc_id, tags, child_params_rsrc_type):
  """Apply tags to image or snapshot, and return boto3 response
  """

  kwargs = {
    TAGS_KWARG: tags,
    child_params_rsrc_type["two_step_tag_id_kwarg"]: (
      [rsrc_id] if child_params_rsrc_type["two_step_tag_id_list"] else rsrc_id
    ),
  }
  return child_params_rsrc_type["two_step_tag_method"](**kwargs)


def ops_perform(ops_rsrcs, date_time_norm_str, svc, rsrc_type):
  """Perform operations on resources of a given type.

  Some boto3 methods can operate on multiple instances, but operating on one
  at a time prevents all-or-nothing failures and facilitates error reporting.
  """

  date_time_norm_str_safe = TRACK_TAG_CHARS_UNSAFE_REGEXP.sub(
    "",
    date_time_norm_str
  )
  for (op, rsrcs) in ops_rsrcs.items():

    parent_params_op = parent_params[svc][rsrc_type]["ops"][op]

    op_method = parent_params_op["method"]
    id_list = parent_params_op["id_list"]
    id_kwarg = (
      parent_params[svc][rsrc_type]["id_key"] + ("s" if id_list else "")
    )
    op_kwargs = parent_params_op["op_kwargs"]

    two_step_tag = parent_params_op["two_step_tag"]
    child_rsrc_type = parent_params_op["child_rsrc_type"]
    if child_rsrc_type:
      child_params_rsrc_type = child_params[svc][child_rsrc_type]
      child_name_kwargs = child_params_rsrc_type["name_kwargs"]

    for (rsrc_id, rsrc) in rsrcs.items():
      kwargs = {id_kwarg: [rsrc_id] if id_list else rsrc_id}
      kwargs.update(op_kwargs)

      if child_rsrc_type:
        child_name = child_name_get(
          rsrc_id,
          rsrc["name_from_tag"],
          date_time_norm_str_safe,
          child_params_rsrc_type
        )
        kwargs.update({
          child_name_kwarg: child_name
          for child_name_kwarg in child_name_kwargs
        })
        rsrc["child_tags"].extend(child_tags_to_add(
          rsrc_id,
          rsrc["name_from_tag"],
          child_name,
          op,
          date_time_norm_str
        ))
        if not two_step_tag:
          kwargs[TAGS_KWARG] = rsrc["child_tags"]

      # Either an exception or the absence of HTTP status code 200
      # is a failure.
      resp = {}
      err_print = ""
      try:
        resp = op_method(**kwargs)
      except botocore.exceptions.ClientError as err:
        err_print = str(err)
      success = boto3_success(resp)
      print(LOG_LINE_FMT.format(
        initiated=int(success),  # 0 is shorter than "False", etc.
        svc=svc,
        rsrc_type=rsrc_type,
        rsrc_id=rsrc_id,
        op=op,
        child_rsrc_type=child_rsrc_type,
        child=child_name if child_rsrc_type else "",
        child_op="",
        note="" if success else (resp if resp else err_print),
      ))

      if two_step_tag and success:
        child_id = child_id_get(resp, child_name, svc, child_rsrc_type)
        resp = {}
        err_print = ""
        if child_id:
          try:
            resp = child_tag(
              child_id,
              rsrc["child_tags"],
              child_params_rsrc_type
            )
          except botocore.exceptions.ClientError as err:
            err_print = str(err)
        success = boto3_success(resp)
        print(LOG_LINE_FMT.format(
          initiated=int(success),  # 0 is shorter than "False", etc.
          svc=svc,
          rsrc_type=rsrc_type,
          rsrc_id=rsrc_id,
          op=op,
          child_rsrc_type=child_rsrc_type,
          child=child_id if child_id else "UNKNOWN",
          child_op="tag",
          note="" if success else (resp if resp else err_print),
        ))

  return


def lambda_handler(event, context):  # pylint: disable=unused-argument
  """Perform scheduled operations on AWS resources, based on tags
  """

  (sched_regexp_lists, date_time_norm_str) = date_time_process(
    datetime.datetime.utcnow()
  )

  # Augment parent_params, the data-driven basis of this code

  for (svc, parent_params_svc) in parent_params.items():
    for (rsrc_type, parent_params_rsrc_type) in parent_params_svc.items():
      tags_op_enable = []
      parent_params_rsrc_type.update({
        "sched_regexps": {},
        "tags_to_op": {},
      })
      for op in parent_params_rsrc_type["ops"].keys():
        tag_op = tag_join(op)
        tags_op_enable.append(tag_op)
        # Operation-enabling tag: require tag, ignore value (see rsrc_process):
        parent_params_rsrc_type["sched_regexps"][tag_op] = []

        for (freq, regexps) in sched_regexp_lists.items():
          tag_op_freq = tag_join(op, freq)
          parent_params_rsrc_type["sched_regexps"][tag_op_freq] = regexps
          # Require an operation's enabling tag and one of its schedule tags:
          parent_params_rsrc_type["tags_to_op"][
            frozenset([tag_op, tag_op_freq])
          ] = op

        # Single-operation identity:
        parent_params_rsrc_type["ops_to_op"][frozenset([op])] = op

      if svc == "ec2":
        # boto3 supports simple (non-regexp) tag filters for EC2
        # (but not for RDS). Using a filter to check for operation-
        # enabling tags may reduce total execution time by preventing
        # some calls to rsrc_process, which must iterate through
        # all tags even if no enabling tags are ultimately found.
        parent_params_rsrc_type["boto3_filters"].append(
          filter_make("tag-key", tags_op_enable)
        )

  if DEBUG:
    pprint.pprint(parent_params)
    print()

  print(re.sub(r"[{}]", "", LOG_LINE_FMT))  # Simple log header
  print(LOG_LINE_FMT.format(  # Log normalized time
    initiated=9,  # Code, to distinguish this from failure (0) or success (1)
    svc="",
    rsrc_type="",
    rsrc_id="",
    op="",
    child_rsrc_type="",
    child="",
    child_op="",
    note=date_time_norm_str,
  ))

  # Iterate over supported AWS services and resource types. Find resources
  # based on tags. Perform each operation on the intended resources.

  for (svc, parent_params_svc) in parent_params.items():
    aws_client = boto3.client(svc)
    methods_set(svc, aws_client)
    for (rsrc_type, parent_params_rsrc_type) in parent_params_svc.items():
      ops_rsrcs = rsrcs_get(
        parent_params_rsrc_type,
        svc,
        rsrc_type,
        aws_client,
      )
      ops_perform(ops_rsrcs, date_time_norm_str, svc, rsrc_type)
    methods_clr(svc)

  return None


if __name__ == "__main__":
  lambda_handler(None, None)
