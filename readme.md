# Start, Reboot, Stop and Back Up AWS Resources with Tags

## Benefits

* **Save money** by stopping EC2 instances and RDS databases during off-hours
* **Take backups** more frequently
* **Use tags** to schedule operations
* Secure tags and backups using Identity and Access Management (IAM) policies
* Install and update easily, with CloudFormation (and optionally, StackSets)

Jump to: [Installation](#quick-start) &bull; [Operation Tags](#enabling-operations) &bull; [Schedule Tags](#scheduling-operations) &bull; [Logging](#output) &bull; [Security](#security-model) &bull; [Multi-region/multi-account](#advanced-installation)

## Comparison with Lifecycle Manager

In July, 2018, Amazon [introduced Data Lifecycle Manager](https://aws.amazon.com/blogs/aws/new-lifecycle-management-for-amazon-ebs-snapshots/). It's a start, but...

 * Tags determine _which_ volumes will be backed up, not _when_. There is a new, single-purpose API for scheduling.
 * Snapshots are taken only every 12 or 24 hours.
 * "Last _x_" snapshot retention is not flexible enough for true archival policies (e.g., keep daily snapshots for a month, plus monthly snapshots for a year).
 * You can create snapshots of single volumes, but not images covering all of an EC2 instance's volumes. Also missing is an option to reboot first.
 * [The same IAM role](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/snapshot-lifecycle.html#dlm-permissions) confers authority to create _and_ delete snapshots, and [anyone who can update a lifecycle policy](https://docs.aws.amazon.com/IAM/latest/UserGuide/list_amazondatalifecyclemanager.html#amazondatalifecyclemanager-UpdateLifecyclePolicy) can reduce the retention period to delete snapshots. These are significant risks, especially in light of the data loss prevention provisions in the European Union General Data Protection Regulation.

By all means, set up Data Lifecycle Manager if you have no automation in place, but consider this project for more flexibility!

## Quick Start

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user.

   _Security Tip:_ To see what you'll be installing, look in the [CloudFormation template](/cloudformation/aws_tag_sched_ops.yaml). <br/>`grep 'Type: "AWS::' aws_tag_sched_ops.yaml | sort | uniq` works well.

2. Go to [Instances](https://console.aws.amazon.com/ec2/v2/home#Instances) in the EC2 Console. Right-click the Name or ID of an instance, select Instance Settings, and then select Add/Edit Tags. Add:

   |Key|Value|Note|
   |--|--|--|
   |`managed-image`||Leave value blank|
   |`managed-image-periodic`|`d=* H:M=11:30`|Replace `11:30` with [current UTC time](https://www.timeanddate.com/worldclock/timezone/utc) + 20 minutes|

3. Go to the [S3 Console](https://console.aws.amazon.com/s3/home). Click the name of the bucket where you keep AWS Lambda function source code. (This may be the same bucket where you keep CloudFormation templates.) If you are creating the bucket now, be sure to create it in the region where you intend to install TagSchedOps; appending the region to the bucket name (for example, `my-bucket-us-east-1`) is recommended. Upload the compressed source code of the AWS Lambda function, [`aws-lambda/aws_tag_sched_ops_perform.py.zip`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws-lambda/aws_tag_sched_ops_perform.py.zip)

   _Security Tip:_ Remove public read and write access from the S3 bucket. Carefully limit write access.

   _Security Tip:_ Download the file from S3 and verify it. (In some cases, you can simply compare the ETag reported by S3.)<br/>`md5sum aws-lambda/aws_tag_sched_ops_perform.py.zip` should match [`aws-lambda/aws_tag_sched_ops_perform.py.zip.md5.txt`](aws-lambda/aws_tag_sched_ops_perform.py.zip.md5.txt)

4. Go to the [CloudFormation Console](https://console.aws.amazon.com/cloudformation/home). Click Create Stack. Click Choose File, immediately below "Upload a template to Amazon S3", and navigate to your locally downloaded copy of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Item|Value|
   |--|--|
   |Stack name|`TagSchedOps`|
   |LambdaCodeS3Bucket|Name of your S3 bucket|
   |MainRegion|Current region, if other than `us-east-1`|

   For all other paramters, keep the default values.

5. After 20 minutes, check [Images](https://console.aws.amazon.com/ec2/v2/home#Images:sort=desc:creationDate) in the EC2 Console.

6. Before deregistering (deleting) the sample image, note its ID, so that you can delete the associated [Snapshots](https://console.aws.amazon.com/ec2/v2/home#Snapshots:sort=desc:startTime). Also untag the instance.

7. Go to [Users](https://console.aws.amazon.com/iam/home#/users) in the IAM Console. Click your regular (uprivileged) username. Click Add Permissions, then click "Attach existing policies directly". In the Search box, type `TagSchedOpsAdminister`. Add the two matching policies.

   _Security Tip_: Review everyone's EC2 and RDS tagging privileges!

8. Log out of the AWS Console. You can now manage relevant tags, view logs, and decode errors, without logging in as a privileged user.

## Warnings

 * Test your backups! Can they be restored successfully?

 * Check that your backups have completed successfully -- or broaden your retention policy to select replacements for missing backups.

 * Weigh the benefits of rebooting against the risks. Rebooting is sometimes necessary for a coherent backup, but a system may stop working afterward.

 * Be aware of AWS charges, including but not limited to: the costs of running the AWS Lambda function, storing CloudWatch logs, and storing images and snapshots; the whole-hour cost when you stop an RDS, EC2 Windows, or EC2 commercial Linux instance (but [other EC2 instances have a 1-minute minimum charge](https://aws.amazon.com/blogs/aws/new-per-second-billing-for-ec2-instances-and-ebs-volumes/)); the ongoing cost of storage for stopped instances; and costs that resume when AWS automatically starts an RDS instance that has been stopped for too many days.

 * Secure your own AWS environment. Test the provided AWS Lambda functions and IAM policies to make sure that they work correctly and meet your expectations. To help improve this project, please submit [bug reports and feature requests](https://github.com/sqlxpert/aws-tag-sched-ops/issues), as well as [proposed changes](https://github.com/sqlxpert/aws-tag-sched-ops/pulls).

## Enabling Operations

* To enable an operation, add a tag from the table. Leave the value blank.

  | |Start|Create Image|Reboot then Create Image|Reboot then Fail Over|Reboot|Create Snapshot|Create Snapshot then Stop|Stop|
  |--|--|--|--|--|--|--|--|--|
  |[EC2 compute instance](https://console.aws.amazon.com/ec2/v2/home#Instances)|`managed-start`|`managed-image`|`managed-reboot-image`| |`managed-reboot`| | |`managed-stop`|
  |[EC2 EBS disk volume](https://console.aws.amazon.com/ec2/v2/home#Volumes)| | | | | |`managed-snapshot`| | |
  |[RDS database instance](https://console.aws.amazon.com/rds/home#dbinstances:)|`managed-start`| | |`managed-reboot-failover`|`managed-reboot`|`managed-snapshot`|`managed-snapshot-stop`|`managed-stop`|

* Also add tags for [repetitive (`-periodic`)](#repetitive-schedules) and/or [one-time (`-once`)](#one-time-schedules) schedules. Prefix with the operation.
* If there are no corresponding schedule tags, an enabling tag will be ignored, and the operation will never occur.
* To temporarily suspend an operation, delete its enabling tag. You may leave its schedule tag(s) in place.
* Examples (for an EC2 or RDS instance):

  |All tags|Operation occurs?|Comment|
  |--|--|--|
  |managed&#x2011;snapshot:&nbsp;&empty;<br/>managed&#x2011;snapshot&#x2011;periodic:&nbsp;u=1&nbsp;H=09&nbsp;M=05|Yes||
  |managed&#x2011;snapshot:&nbsp;&empty;<br/>managed&#x2011;snapshot&#x2011;once:&nbsp;2017-12-31T09:05|Yes||
  |managed&#x2011;snapshot:&nbsp;&empty;<br/>managed&#x2011;snapshot&#x2011;periodic:&nbsp;u=1&nbsp;H=09&nbsp;M=05 <br/>managed&#x2011;snapshot&#x2011;once:&nbsp;2017-12-31T09:05|Yes|Both repetitive and one-time schedule tags are allowed|
  |managed&#x2011;snapshot:&nbsp;No <br/>managed&#x2011;snapshot&#x2011;periodic:&nbsp;u=1&nbsp;H=09&nbsp;M=05|Yes|The value of an enabling tag is always ignored|
  |managed&#x2011;snapshot:&nbsp;&empty;|No|No schedule tag is present|
  |managed&#x2011;snapshot&#x2011;once:&nbsp;2017-12-31T09:05|No|No enabling tag is present (operation is suspended)|
  |managed&#x2011;snapshot:&nbsp;&empty;<br/>managed&#x2011;snapshot&#x2011;once:&nbsp;&empty;|No|Schedule is invalid (blank)|
  |managed&#x2011;snapshot:&nbsp;&empty;<br/>managed&#x2011;snapshot&#x2011;periodic:&nbsp;Monday|No|Schedule is invalid|
  |managed&#x2011;snapshot:&nbsp;&empty;<br/>managed&#x2011;stop&#x2011;periodic:&nbsp;u=1&nbsp;H=09&nbsp;M=05|No|The enabling tag and the schedule tag are for different operations|

  Each tag is shown in _key:value_ form. &empty; means that the value is blank.

## Scheduling Operations

 * All times are UTC, on a 24-hour clock.
 * The function runs once every 10 minutes. The last digit of the minute is always ignored. For example, `M=47` means _one time, between 40 and 50 minutes after the hour_.
 * Month and minute values must have two digits. Use a leading zero if necessary. (Weekday numbers have only one digit.)
 * Use a comma (`,`) or a space (` `) to separate components. (RDS does not allow commas in tag values.) The order of components within a tag value does not matter.
 * `T` separates date from time; it is invariable.
 * [Repetitive (`-periodic`)](#repetitive-schedules) and [one-time (`-once`)](#one-time-schedules) schedule tags are supported. Prefix with the operation.
 * If the corresponding [enabling tag](#enabling-operations) is missing, schedule tags will be ignored, and the operation will never occur.

### Repetitive Schedules

  * Tag suffix: `-periodic`

  * Values: one or more of the following components:

    |Name|Minimum|Maximum|Wildcard|Combines With|
    |--|--|--|--|--|
    |Day of month (`d`)|`d=01`|`d=31`|`d=*`|`H` and `M`, or `H:M`|
    |Weekday (`u`)|`u=1` (Monday)|`u=7` (Sunday)||`H` and `M`, or `H:M`|
    |Hour (`H`)|`H=00`|`H=23`|`H=*`|`d` or `u`, and `M`|
    |Minute (`M`)|`M=00`|`M=59`||`d` or `u`, and `H`|
    |Hour and minute (`H:M`)|`H:M=00:00`|`H:M=23:59`||`d` or `u`|
    |Day of month, hour and minute (`dTH:M`)|`dTH:M=01T00:00`|`dTH:M=31T23:59`|||
    |Weekday, hour and minute (`uTH:M`)|`uTH:M=1T00:00`|`uTH:M=7T23:59`|||

      * To be valid, a component or combination of components must specify a day, hour and minute.
      * Repeat a whole component to specify multiple values. For example, `d=01,d=11,d=21` means the 1st, 11th and 21st days of the month.
      * The `*` wildcard is allowed for day (_every day of the month_) and hour (_every hour of the day_).
      * For consistent one-day-a-month scheduling, avoid `d=29` through `d=31`.
      * Label letters match [`strftime`](http://manpages.ubuntu.com/manpages/xenial/man3/strftime.3.html) and weekday numbers are [ISO 8601-standard](https://en.wikipedia.org/wiki/ISO_8601#Week_dates) (different from `cron`).

  * Examples:

    |Value of Repetitive Schedule Tag|Demonstrates|Operation Begins|
    |--|--|--|
    |dTH:M=\*T14:25|Once-a-day event|Between 14:20 and 14:30, every day.|
    |uTH:M=1T14:25|Once-a-week event|Between 14:20 and 14:30, every Monday.|
    |dTH:M=28T14:25|Once-a-month event|Between 14:20 and 14:30 on the 28th day of every month.|
    |d=1&nbsp;d=8&nbsp;d=15&nbsp;d=22&nbsp;H=03&nbsp;H=19&nbsp;M=01|`cron` schedule|Between 03:00 and 03:10 and again between 19:00 and 19:10, on the 1st, 8th, 15th, and 22nd days of every month.|
    |d=\*&nbsp;H=\*&nbsp;M=15&nbsp;M=45&nbsp;H:M=08:50|Extra daily event|Between 10 and 20 minutes after the hour and 40 to 50 minutes after the hour, every hour of every day, _and also_ every day between 08:50 and 09:00.|
    |d=\*&nbsp;H=11&nbsp;M=00&nbsp;uTH:M=2T03:30&nbsp;uTH:M=5T07:20|Two extra weekly events|Between 11:00 and 11:10 every day, _and also_ every Tuesday between 03:30 and 03:40 and every Friday between 07:20 and 7:30.|
    |u=3&nbsp;H=22&nbsp;M=15&nbsp;dTH:M=01T05:20|Extra monthly event|Between 22:10 and 22:20 every Wednesday, _and also_ on the first day of every month between 05:20 and 05:30.|

### One-Time Schedules

  * Tag suffix: `-once`

  * Values: one or more [ISO 8601 combined date and time strings](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations), of the form `2017-03-21T22:40` (March 21, 2017, in this example)
      * Remember, the code runs once every 10 minutes and the last digit of the minute is ignored
      * Omit seconds and fractions of seconds
      * Omit time zone; UTC is always used

## Output

* After logging in to the [AWS Web Console](https://signin.aws.amazon.com/console), go to the [Log Group for the AWS Lambda function](https://console.aws.amazon.com/cloudwatch/home#logs:prefix=/aws/lambda/TagSchedOps-TagSchedOpsPerformLambdaFn-), in the CloudWatch Logs Console. If you gave the CloudFormation stack a name other than `TagSchedOps`, check the list of [Log Groups for _all_ AWS Lambda functions](https://console.aws.amazon.com/cloudwatch/home#logs:prefix=/aws/lambda/) instead.

* Sample output:

  |`initiated`|`rsrc_id`|`op`|`child_rsrc_type`|`child`|`child_op`|`note`|
  |--|--|--|--|--|--|--|
  |`9`||||||`2017-09-12T20:40`|
  |`1`|`i-08abefc70375d36e8`|`reboot-image`|`Image`|`zm-my-server-20170912T2040-83xx7`|||
  |`1`|`i-08abefc70375d36e8`|`reboot-image`|`Image`|`ami-bc9fcbc6`|`tag`||
  |`1`|`i-04d2c0140da5bb13e`|`start`|||||
  |`0`|`i-09cdea279388d35a2`|`start,stop`||||`OPS_UNSUPPORTED`|
  |`0`|`my-database`|`reboot-failover`||||...`ForceFailover cannot be specified`...|

  _This run began September 12, 2017 between 20:40 and 20:50 UTC. An EC2 instance (ID prefix `i-`) is being rebooted and backed up, but the instance may not yet be ready again, and the image may not yet be complete; the image is named `zm-my-server-20170912T2040-83xx7`. The image has received ID `ami-bc9fcbc6`, and has been tagged. A different EC2 instance is starting up, but may not yet be ready. A third EC2 instance is tagged for simultaneous start and stop, a combination that is not supported. An RDS database instance (no `i-` or `vol-` ID prefix) could not be rebooted with fail-over. (The full error message goes on to explain that it is not multi-zone.)_

* There is a header line, an information line, and one line for each operation requested. (Tagging is usually a separate operation.)

* Values are tab-separated (but the CloudWatch Logs Console seems to collapse multiple tabs).

* Columns and standard values:

  |`initiated`|`rsrc_id`|`op`|`child_rsrc_type`|`child`|`child_op`|`note`|
  |--|--|--|--|--|--|--|
  |Operation initiated?|Resource ID|Operation|Child type|Pointer to child|Child operation|Message|
  |`0`&nbsp;No <br/>`1`&nbsp;Yes <br/>`9`&nbsp;_Info.&nbsp;only_|`i-`&nbsp;EC2&nbsp;instance&nbsp;ID <br/>`vol-`&nbsp;EBS&nbsp;volume&nbsp;ID <br/>RDS&nbsp;instance&nbsp;name|_See_ [_table_](#enabling-operations)|`Image` <br/>`Snapshot` <br/>`DBSnapshot`|_Name, ID, or ARN, as available_|`tag`||

* Although the TagSchedOpsAdminister and TagSchedOpsTagSchedule policies authorize read-only access to the logs via the AWS API, and seem to be sufficient for using the links provided above, users who are not AWS administrators may also want [additional privileges for the CloudWatch Console](http://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/iam-identity-based-access-control-cwl.html#console-permissions-cwl).

### Debugging Mode

If the `DEBUG` environment variable is set, the function outputs internal reference data, including the regular expressions used to match schedule tags.

To use the debugging mode,

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user. AWS Lambda treats changes to environment variables like changes to code.

2. Click on the [TagSchedOpsPerformLambdaFn AWS Lambda function](https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions?f0=a3c%3D%3AVGFnU2NoZWRPcHNQZXJmb3JtTGFtYmRhRm4%3D).

3. Open the Code tab and scroll to the bottom. In the "Environment variables" section, type `DEBUG` in the first empty Key box. Leave Value blank.

4. <a name="debug-step-4"></a>Scroll back to the top and click the white Save button. _Do not click the orange "Save and test" button_; that would cause the function to run more than once in the same 10-minute interval.

5. After 10 minutes, find the debugging information in [CloudWatch Logs](#output).

6. Turn off debugging mode right away, because the extra information is lengthy. Back on the Code tab, scroll down and click Remove, to the far right of `DEBUG`. Repeat [Step 4](#debug-step-4) to save.

## On/Off Switch

* The TagSchedOpsAdminister policies authorize turning the function on or off completely.

* After logging in to the [AWS Web Console](https://signin.aws.amazon.com/console), go to [Rules](https://console.aws.amazon.com/cloudwatch/home#rules:) in the CloudWatch Events Console. Click the radio button to the left of TagSchedOpsPerform10MinEventRule, then select Enable or Disable from the Actions pop-up menu, next to the blue "Create rule" button.

* This toggle is per-region and per-AWS-account.

* Missed operations will not occur when the function is turned back on; there is no queue or backlog.

## Child Resources

Some operations create a child resource (image or snapshot) from a parent resource (instance or volume).

### Naming

* The name of the child consists of these parts, separated by hyphens (`-`):

  |#|Part|Example|Purpose|
  |--|--|--|--|
  |1|Prefix|`zm`|Identifies and groups children created by this project, for interfaces that do not expose tags. `z` will sort after most manually-created images and snapshots. `m` stands for "managed".|
  |2|Parent name or identifier|`webserver`|Conveniently indicates the parent. Derived from the `Name` tag (if not blank), the logical name (if supported), or the physical identifier (as a last resort). Multiple children of the same parent will sort together, by creation date (see next row).|
  |3|Date/time|`20171231T1400Z`|Indicates when the child was created. Always includes the `Z` suffix to indicate UTC. The last digit of the minute is normalized to 0. The `-` and `:` separators are removed for brevity, and because AWS does not allow `:` in resource names. (The [`managed-date-time` tag](#tag-managed-date-time) preserves the separators.)|
  |4|Random string|`g3a8a`|Guarantees unique names. Five characters are chosen from a small set of unambiguous letters and numbers.|

* If parsing is ever necessary, keep in mind that the second part may contain internal hyphens.
* This project replaces characters forbidden by AWS with `X`.
* For some resource types, the description is also set to the name, in case interfaces expose only one or the other.

### Special Tags

* Special tags are added to the child:

  |Tag(s)|Purpose|
  |--|--|
  |`Name`|Supplements EC2 resource identifier. The key is renamed `managed-parent-name` when the value is passed from parent to child, because the child has a `Name` tag of its own. The code handles `Name` specially for both EC2 and RDS, in case AWS someday extends EC2-style tag semantics to RDS.|
  |`managed-parent-name`|The `Name` tag value from the parent. May be blank.|
  |`managed-parent-id`|The identifier of the parent instance or volume. AWS stores this in metadata for some but not all resource types, and the retrieval key differs for each resource type.|
  |`managed-origin`|The operation (for example, `snapshot`) that created the child. Identifies resources created by this project. Also distinguishes special cases, such as whether an EC2 instance was or was not rebooted before an image was created.|
  |<a name="tag-managed-date-time">`managed-date-time`</a>|Groups resources created during the same 10-minute interval. The last digit of the minute is normalized to 0, and `Z` is always appended, to indicate UTC. AWS stores the _exact_ time (too specific for grouping) in metadata, and the retrieval key and the format differ for each resource type!|

* Tags other than operation-enabling tags, schedule tags, and the `Name` tag, are copied from parent to child. (The deletion tag, `managed-delete`, would not make sense on instances and volumes, but if it is present, it is not copied to images and snapshots.)

## Operation Combinations

Multiple _non-simultaneous_ operations on the same resource are allowed.

### Supported Combinations

If two or more operations on the same resource are scheduled for the same 10-minute interval, the function combines them, where possible:

|Resource|Simultaneous Operations|Effect|
|--|--|--|
|EC2 instance|Create Image + Reboot|Reboot then Create Image|
|EC2 or RDS instance|Stop + Reboot|Stop|
|RDS instance|Stop + Create Snapshot|Create Snapshot then Stop|

The Create Image + Reboot combination for EC2 instances is useful. For example, you could take hourly backups but reboot only in conjunction with the midnight backup. The midnight backup would be guaranteed to be coherent for all files, but you could safely retrieve static files as of any given hour, from the other backups. To set up this example:

|Tag|Value|
|--|--|
|`managed-image`||
|`managed-image-periodic`|`d=*,H=*,M=59`|
|`managed-reboot`||
|`managed-reboot-periodic`|`d=*,H=23,M=59`|

23:59, which for the purposes of this project represents the last 10-minute interval of the day, is the unambiguous way to express _almost the end of some designated day_, on any system. 00:00 and 24:00 could refer to the start or the end of the designated day, and not all systems accept 24:00, in any case. Remember that all times are UTC; adjust for night-time in your time zone!

### Unsupported Combinations

Resources tagged for unsupported combinations of operations are logged (with message `OPS_UNSUPPORTED`) and skipped.

|Bad Combination|Reason|Example|
|--|--|--|
|Mutually exclusive operations|The operations conflict.|Start + Stop|
|Choice of operation depends on current state of instance|The state of the instance could change between the status query and the operation request.|Start + Reboot|
|Sequential or dependent operations|The logical order cannot always be inferred. Also, operations proceed asynchronously; one might not complete in time for another to begin. Note that Reboot then Create Image (EC2 instance) and Create Snapshot then Stop (RDS instance) are _single_ AWS operations.|Start + Create Image|

## Security Model

 * Prevent unauthorized changes to the AWS Lambda function by attaching the TagSchedOpsPerformLambdaFnProtect IAM policy to most IAM users and roles with write privileges for:
     * AWS Lambda
     * CloudFormation Events
     * CloudFormation Logs
     * IAM (roles and/or policies)

 * Allow only a few trusted users to tag EC2 and RDS resources, because tags determine which resources are started, backed up, rebooted, and stopped.

 * Tag backups for deletion, but let a special IAM user or role actually delete them. To mark images and snapshots for (manual) deletion, add the `managed-delete` tag.

 * Do not allow the same IAM users and roles that create backups to delete backups (or even to tag them for deletion).

 * Choose from a library of IAM policies:

   |Policy Name|Manage Enabling Tags|Manage One-Time Schedule Tags|Manage Repetitive Schedule Tags|Back Up|Manage Deletion Tag|Delete|
   |--|--|--|--|--|--|--|
   |_Scope &rarr;_|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Images, Snapshots_|_Images, Snapshots_|
   |TagSchedOpsAdminister|Allow|Allow|Allow|No effect|Deny|Deny|
   |TagSchedOpsTagScheduleOnce|Deny [<sup>i</sup>](#policy-footnote-1)|Allow [<sup>ii</sup>](#policy-footnote-1)|Deny|No effect|Deny|Deny|
   |TagSchedOpsTagForDeletion|Deny|Deny|Deny|Deny|Allow|Deny|
   |TagSchedOpsBackupDelete|Deny|Deny|Deny|Deny|Deny|Allow|
   |TagSchedOpsNoTag|Deny|Deny|Deny|No effect|Deny|Deny|

   Footnotes:

     1. <a name="policy-footnote-1"></a>Enabling tag required. For example, a user could add `managed-image-once` to an EC2 instance only if the `managed-image` tag were already present.

   These policies cover all regions. If you use regions to differentiate production and non-production resources, modify copies of the provided policies.

   Because Deny always takes precendence in IAM, some policy combinations conflict.

   In some cases, you must add, change or delete one tag at a time.

 * Although the TagSchedOpsAdminister and TagSchedOpsTag policies authorize tagging via the AWS API, users who are not AWS administrators may also want:

     * [AmazonEC2ReadOnlyAccess](https://console.aws.amazon.com/iam/home#policies/arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess), to use the EC2 Console
     * [AmazonRDSReadOnlyAccess](https://console.aws.amazon.com/iam/home#policies/arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess), to use the RDS Console

 * You may have to [decode authorization errors](http://docs.aws.amazon.com/cli/latest/reference/sts/decode-authorization-message.html). The TagSchedOpsAdminister and TagSchedOpsTag policies grant the necessary privilege.

 * Note these AWS technical limitations/oversights:

    * An IAM user or role that can create an image of an EC2 instance can force a reboot by omitting the `NoReboot` option. (Explicitly denying the reboot privilege does not help.) The unavoidable pairing of a harmless privilege, taking a backup, with a risky one, rebooting, is unfortunate.

    * Tags are ignored when deleting EC2 images and snapshots. Limit EC2 image and snapshot deletion privileges -- even Ec2TagSchedOpsDelete -- to highly-trusted IAM users and roles.

    * In RDS, an IAM user or role that can add specific tags can add _any other_ tags in the same request. Limit RDS tagging privileges -- even the policies provided here -- to highly-trusted users and roles.

## Advanced Installation

Before starting a multi-region and/or multi-account installation, check all regions, in all AWS accounts, for TagSchedOps CloudFormation stacks created using the Quick Start instructions. Delete them now.

### Multi-Region Configuration

If you intend to install TagSchedOps in multiple regions,

1. Create S3 buckets in all [regions](http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region) where you intend to install TagSchedOps. The bucket names must share the same prefix, followed by a hyphen (`-`) and a suffix for the region. The region in which each bucket is created _must_ match the suffix in the bucket's name.

2. Upload [`aws-lambda/aws_tag_sched_ops_perform.py.zip`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws-lambda/aws_tag_sched_ops_perform.py.zip) to each bucket. The need for copies in multiple regions is an AWS Lambda limitation.

3. Keep the following rules in mind when setting parameters, later:

   |Parameter|Value|
   |--|--|
   |LambdaCodeS3Bucket|_Use the shared prefix; for example, if you created_ `my-bucket-us-east-1` _and_ `my-bucket-us-west-2` _, use_ `my-bucket`|
   |MainRegion|_Always use the same value, to prevent the creation of duplicate sets of user policies_|
   |StackSetsOrMultiRegion|Yes|
   |TagSchedOpsPerformCodeS3VersionID|_Leave blank, because the value would differ in every region; only the latest version of the AWS Lambda function source code file in each region's S3 bucket can be used_|

### Multi-Account Configuration

If you intend to install TagSchedOps in multiple AWS accounts,

1. In every target AWS account, create [`cloudformation/tag-sched-ops-install.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops-install.yaml). Set:

   |Item|Value|
   |--|--|
   |Stack name|`TagSchedOpsInstall`|
   |AWSCloudFormationStackSet*Exec*utionRoleStatus|_Choose carefully!_|
   |AdministratorAccountId|AWS account number of main (or only) account; leave blank if AWSCloudFormationStackSet*Exec*utionRole existed before this stack was created|
   |LambdaCodeS3Bucket|Name of AWS Lambda function source code bucket (shared prefix, in a multi-region scenario)|

2. For the AWS Lambda function source code S3 bucket in *each region*, create a bucket policy allowing access by *every target AWS account*'s AWSCloudFormationStackSetExecutionRole (StackSet installation) or TagSchedOpsCloudFormation role (manual installation with ordinary CloudFormation). The full name of the TagSchedOpsCloudFormation role will vary; for every target AWS account, look up the random suffix in the [list of IAM roles](https://console.aws.amazon.com/iam/home#/roles) or by selecting the TagSchedOpsInstall stack in the [list of CloudFormation stacks](https://us-east-2.console.aws.amazon.com/cloudformation/home#/stacks) and drilling down to  Resources. S3 bucket policy template:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": [
             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_1:role/AWSCloudFormationStackSetExecutionRole",
             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_1:role/TagSchedOpsInstall-TagSchedOpsCloudFormation-RANDOM_SUFFIX_1",

             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_2:role/AWSCloudFormationStackSetExecutionRole",
             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_2:role/TagSchedOpsInstall-TagSchedOpsCloudFormation-RANDOM_SUFFIX_2"

           ]
         },
         "Action": [
           "s3:GetObject",
           "s3:GetObjectVersion"
         ],
         "Resource": "arn:aws:s3:::BUCKET_NAME/*"
       }
     ]
   }
   ```

### CloudFormation Stack*Set* Installation

1. Follow the [multi-region steps](#multi-region-configuration), even for a multi-account, single-region scenario.

2. Follow the [multi-account steps](#multi-account-configuration). In a single-account, multi-region scenario, no S3 bucket policy is needed.

3. If [StackSets](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html) has never been used, create [AWSCloudFormationStackSet*Admin*istrationRole](https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetAdministrationRole.yml). Do this one time, in your main (multi-account scenario) or only (single-account scenario) AWS account. There is no need to create AWSCloudFormationStackSet*Exec*utionRole using Amazon's template; the TagSchedOps*Install* stack provides it, when necessary.

4. In the AWS account with the AWSCloudFormationStackSet*Admin*istrationRole, go to the [StackSets Console](https://console.aws.amazon.com/cloudformation/stacksets/home#/stacksets).

5. Click Create StackSet, then select "Upload a template to Amazon S3", then click Browse and select your locally downloaded copy of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Item|Value|
   |--|--|
   |StackSet name|`TagSchedOps`|
   |LambdaCodeS3Bucket|_Use the shared prefix; for example, if you created_ `my-bucket-us-east-1` _, use use_ `my-bucket`|
   |MainRegion|_Must be a StackSet target region_|
   |StackSetsOrMultiRegion|Yes|
   |TagSchedOpsPerformCodeS3VersionID|_In a multi-region scenario, leave blank_|

6. On the next page, specify the target AWS accounts, typically by entering account numbers below "Deploy stacks in accounts". Then, move the target region(s) from "Available regions" to "Deployment order". It is a good idea to put the main region first.

### Manual Installation

Manual installation is adequate if the number of installations is small, but keeping more than one installation up-to-date could be difficult.

1. Follow the [multi-region steps](#multi-region-configuration), if applicable.

2. Follow the [multi-account steps](#multi-account-configuration), if applicable.

3. Follow the [Quick Start](#quick-start) installation steps in each target region and/or target AWS account. Set parameters based on the multi-region and/or multi-account rules.

    * In a multi-account scenario, select the TagSchedOpsCloudFormation IAM Role during this step; CloudFormation may not be able to create the stack without assuming this role.

      If the user invoking CloudFormation is not an administrator, attach the following policies to the user beforhand:

      |Policy|Source|
      |--|--|
      |[AmazonS3FullAccess](https://console.aws.amazon.com/iam/home?#/policies/arn:aws:iam::aws:policy/AmazonS3FullAccess)|AWS|
      |[AmazonSNSReadOnlyAccess](https://console.aws.amazon.com/iam/home?#/policies/arn:aws:iam::aws:policy/AmazonSNSReadOnlyAccess)|AWS|
      |[IAMReadOnlyAccess](https://console.aws.amazon.com/iam/home?#/policies/arn:aws:iam::aws:policy/IAMReadOnlyAccess)|AWS|
      |TagSchedOpsCloudFormationRolePass|TagSchedOpsInstall stack|
      |CloudFormationFullAccess|TagSchedOpsInstall stack|

      Detach these policies -- particularly AmazonS3FullAccess and CloudFormationFullAccess -- after the stack has been created. AWS does not publish the _minimum_ privileges needed to create a stack. Full S3 access is obviously risky, and full CloudFormation access allows a non-administrator to modify or delete _any_ stack with an IAM Role.

## Software Updates

New versions of the AWS Lambda function source code and the CloudFormation template will be released from time to time.

### CloudFormation Stack Update

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user.

2. Go to the [S3 Console](https://console.aws.amazon.com/s3/home). Click the name of the bucket where you keep CloudFormation templates and their dependencies. Open the Properties tab. If Versioning is disabled, click anywhere inside the box, select "Enable versioning", and click Save.

3. Open the Overview tab. Upload the latest version of
[`aws-lambda/aws_tag_sched_ops_perform.py.zip`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws-lambda/aws_tag_sched_ops_perform.py.zip) to S3.

4. Click the checkbox to the left of the newly-uploaded file. In the window that pops up, look below the Download button and reselect "Latest version". In the Overview section of the pop-up window, find the Link and copy the text _after_ `versionId=`. (The Version ID will not appear unless you expressly select "Latest version".)

   _Security Tip:_ Download the file from S3 and verify it. (In some cases, you can simply compare the ETag reported by S3.) <br/>`md5sum aws-lambda/aws_tag_sched_ops_perform.py.zip` should match [`aws-lambda/aws_tag_sched_ops_perform.py.zip.md5.txt`](aws-lambda/aws_tag_sched_ops_perform.py.zip.md5.txt)

5. Go to [Stacks](https://console.aws.amazon.com/cloudformation/home#/stacks) in the CloudFormation Console. Click the checkbox to the left of `TagSchedOps` (you might have given the stack a different name). From the Actions pop-up menu next to the blue Create Stack button, select Create Change Set For Current Stack.

6. Click Choose File, immediately below "Upload a template to Amazon S3", and navigate to your locally downloaded copy of the latest version of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Item|Value|
   |--|--|
   |Change set name|_Type a name of your choice_|
   |TagSchedOpsPerformCodeS3VersionID|_Paste the Version ID, from S3_|

   _A different S3 Version ID makes CloudFormation recognize new AWS Lambda function source code. Once you are familiar with the full update procedure, you may skip Steps 2-5 and leave TagSchedOpsPerformCodeS3VersionID as it was, when you are certain that only the CloudFormation template, not the function source code, is changing._

7. Click through the remaining steps. Finally, click "Create change set".

8. In the Changes section, check the Replacement column.

   If True is shown on any row, check the Logical ID.

   1. If the resource is for internal use, ignore it.

   2. If, however, it a user policy, such as TagSchedOpsAdminister, open another Web browser window, go to [Policies](https://console.aws.amazon.com/iam/home#/policies) in the IAM Console, click the name of the policy, open the "Attached entities" tab, and detach the policy from all entities. Keep notes!

9. Click Execute, below the top-right corner of the CloudFormation Console window.

10. Refresh until the stack's status shows `UPDATE_COMPLETE`, in green.

11. If you had to detach any IAM policies, return to the IAM Console and attach the replacement policies to the original entities.

12. If TagSchedOps is installed in multiple regions, repeat the update steps in each region. The S3 Version IDs will differ.

### CloudFormation Stack*Set* Update

Differences when updating a StackSet instead of an ordinary stack:

 * Click the radio button to the left of TagSchedOps, in the [list of StackSets](https://console.aws.amazon.com/cloudformation/stacksets/home#/stacksets). From the Actions pop-up menu next to the blue Create StackSet button, select "Manage stacks in StackSet". Then, select "Edit stacks". On the next page, select "Upload a template to Amazon S3" and upload the latest version of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml).

 * A single update covers all target regions and/or AWS target accounts.

 * The TagSchedOpsPerformCodeS3VersionID parameter must remain blank. So that CloudFormation will recognize new source code for the AWS Lambda function, rename `aws-lambda/aws_tag_sched_ops_perform.py.zip` to `aws-lambda/aws_tag_sched_ops_perform_20170924.py.zip` (substitute current date) before uploading the file to the regional S3 bucket(s). Change the TagSchedOpsPerformCodeName parameter accordingly.

 * Change Sets are not supported. There is no preliminary feedback about the scope of changes.

## Future Work

 * Automated testing, consisting of a CloudFormation template to create sample AWS resources, and a program (perhaps another AWS Lambda function!) to check whether the intended operations were performed. An AWS Lambda function would also be ideal for testing security policies, while cycling through different IAM roles.

 * Additional AWS Lambda function, to automatically delete backups tagged `managed-delete`

 * Makefile

 * Tags and reference dictionary updates to support scheduled restoration of images and snapshots (for backup testing?)

## Dedication

This work is dedicated to [Ernie Salazar](https://github.com/ehsalazar), R&eacute;gis and Marianne Marcelin, and my wonderful colleagues of the past few years.

## Licensing

|Scope|License|Copy Included|
|--|--|--|
|Source code files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Source code within documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Documentation files (including this readme file)|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|[zlicense-doc.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-doc.txt)|

Copyright 2018, Paul Marcelin

Contact: `marcelin` at `cmu.edu` (replace at with `@`)
